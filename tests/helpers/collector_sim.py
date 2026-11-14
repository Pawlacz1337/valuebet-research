"""Symulator świata dla testu niezmiennika kolektora (FSA #0e, decyzja Pawła pkt 2).

Świat z ziarnem: mecze z historią listowania w ``/events`` i godzin gwizdka,
licznik kredytów, przerwy w pracy komputera, mało miejsca na dysku, błędy
zapisu. Kolektor to **prawdziwy** ``run_once`` wołany co 5 minut fałszywego
zegara, przez fałszywy transport HTTP.

Wyrocznia nie czyta stanu kolektora — patrzy na to, co transport naprawdę
zwrócił i czy zapis do raw się udał. Kolektor ma tylko dwie uczciwe
odpowiedzi na każdy mecz objęty niezmiennikiem: zamknięcie w [KO-30, KO]
albo ``closing_missed`` z powodem z zamkniętej listy, który jest PRAWDZIWY
w tym świecie (np. „komputer nie działał” tylko wtedy, gdy rzeczywiście
opuścił przebieg w godzinie przed gwizdkiem).
"""

from __future__ import annotations

import errno
import json
import random
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import httpx

from helpers import build, fake_http
from valuebet.ingest.odds_api import OddsApiClient, OddsApiSettings
from valuebet.ingest.odds_collector import LEAGUES, OddsCollector
from valuebet.ingest.raw_store import RawStore

STEP = timedelta(minutes=5)
#: Mecz objęty niezmiennikiem: listowany z ostateczną godziną ≥ 60 min przed gwizdkiem.
LISTED_BEFORE = timedelta(minutes=60)
CLOSING_SPAN = timedelta(minutes=30)
BUDGET = 450
LOW_DISK = 100 * 1024 * 1024
#: Zamknięta lista powodów z decyzji Pawła (2026-10-03, pkt 2) plus dwa
#: zaakceptowane warunkowo (2026-10-04 pkt 2, 2026-10-07): błąd API dostawcy
#: (5xx, timeout, zerwane połączenie) i błąd kolektora (HTTP 4xx poza 429).
REASON_OFFLINE = "komputer nie działał"
REASON_BUDGET = "budżet > 450"
REASON_NO_PINNACLE = "brak rynku Pinnacle"
REASON_STORAGE = "brak miejsca / błąd zapisu"
REASON_API = "błąd API dostawcy"
REASON_CLIENT = "błąd kolektora (HTTP 4xx)"
REASON_CONTRACT = "błąd kontraktu API"
REASONS = (
    REASON_OFFLINE,
    REASON_BUDGET,
    REASON_NO_PINNACLE,
    REASON_STORAGE,
    REASON_API,
    REASON_CLIENT,
    REASON_CONTRACT,
)
CONTRACT = "contract"
#: Rodzaje awarii ``/odds`` w generatorze: kod HTTP albo awaria transportu.
PROVIDER_FAILURES = ("500", "502", "503", "timeout", "reset")
CLIENT_FAILURES = ("400", "401", "403", "404")
RATE_LIMIT = "429"

H2H = {
    "key": "h2h",
    "outcomes": [
        {"name": "H", "price": 2.10},
        {"name": "A", "price": 3.40},
        {"name": "D", "price": 3.30},
    ],
}


def _iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def _overlaps(windows: list[tuple[datetime, datetime]], a: datetime, b: datetime) -> bool:
    return any(x < b and a < y for x, y in windows)


@dataclass
class SimMatch:
    event_id: str
    sport: str
    listed_at: datetime
    #: (od kiedy obowiązuje, gwizdek) — pierwsza pozycja od ``listed_at``.
    schedule: list[tuple[datetime, datetime]]
    pinnacle: bool

    def kickoff_at(self, t: datetime) -> datetime:
        current = self.schedule[0][1]
        for since, kickoff in self.schedule:
            if since <= t:
                current = kickoff
        return current

    @property
    def kickoff(self) -> datetime:
        return self.schedule[-1][1]

    @property
    def final_listed_at(self) -> datetime:
        return max(self.listed_at, self.schedule[-1][0])

    @property
    def covered(self) -> bool:
        return self.final_listed_at <= self.kickoff - LISTED_BEFORE

    def listed(self, t: datetime) -> bool:
        return self.listed_at <= t < self.kickoff_at(t) + timedelta(hours=2)


@dataclass
class PaidCall:
    at: datetime
    sport: str
    cost: int
    #: (event_id, gwizdek) z kompletnym h2h Pinnacle w odpowiedzi.
    priced: set[tuple[str, datetime]]
    written: bool | None = None


@dataclass
class World:
    seed: int
    start: datetime
    end: datetime
    offset: timedelta
    matches: list[SimMatch]
    used0: int
    offline: list[tuple[datetime, datetime]]
    disk_low: list[tuple[datetime, datetime]]
    write_fail: list[tuple[datetime, datetime]]
    kinds: list[str]
    #: (od, do, rodzaj) — awarie płatnego ``/odds``: kod HTTP, ``timeout``, ``reset``.
    api_fail: list[tuple[datetime, datetime, str]] = field(default_factory=list)
    #: (od, do, rodzaj) — awarie bezpłatnego ``/sports`` (licznik nieznany).
    sports_fail: list[tuple[datetime, datetime, str]] = field(default_factory=list)
    now: datetime = field(init=False)
    used: int = field(init=False)
    paid: list[PaidCall] = field(default_factory=list)
    used_at: dict[datetime, int] = field(default_factory=dict)
    ticks_run: list[datetime] = field(default_factory=list)
    #: (chwila, liga, {id: gwizdek na liście}) — każde wywołanie ``/events``.
    events_calls: list[tuple[datetime, str, dict[str, datetime]]] = field(default_factory=list)
    events_last_header: list[int | None] = field(default_factory=list)
    #: Mecze wyłączone przez zawężenie (niepoznawalne) — licznik dla testu.
    excluded: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.now = self.start
        self.used = self.used0

    # -- świat w chwili ``now`` -------------------------------------------

    def listing(self, sport: str, *, priced: bool) -> list[dict[str, Any]]:
        out = []
        for m in self.matches:
            if m.sport != sport or not m.listed(self.now):
                continue
            books = [{"key": "pinnacle", "markets": [H2H]}] if priced and m.pinnacle else []
            out.append(
                {
                    "id": m.event_id,
                    "sport_key": sport,
                    "commence_time": _iso(m.kickoff_at(self.now)),
                    "home_team": f"H-{m.event_id}",
                    "away_team": f"A-{m.event_id}",
                    "bookmakers": books,
                }
            )
        return out

    def disk_is_low(self) -> bool:
        return _overlaps(self.disk_low, self.now, self.now + timedelta(seconds=1))

    def api_failure(self, spans: list[tuple[datetime, datetime, str]] | None = None) -> str | None:
        for a, b, kind in self.api_fail if spans is None else spans:
            if a <= self.now < b:
                return kind
        return None

    def failure_response(self, request: httpx.Request, failure: str) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("symulacja", request=request)
        if failure == "reset":
            raise httpx.ConnectError("symulacja: połączenie zerwane", request=request)
        if failure == CONTRACT:
            return httpx.Response(200, json={"message": "symulacja: zły kształt"})
        return httpx.Response(int(failure), text=f"symulacja {failure}")

    def write_fails(self) -> bool:
        return self.disk_is_low() or _overlaps(
            self.write_fail, self.now, self.now + timedelta(seconds=1)
        )

    # -- transport ----------------------------------------------------------

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        base = {"x-requests-used": str(self.used), "x-requests-remaining": str(500 - self.used)}
        if path.endswith("/robots.txt"):
            return httpx.Response(404, text="")
        if path.endswith("/sports") or path.endswith("/sports/"):
            failure = self.api_failure(self.sports_fail)
            if failure is not None:
                return self.failure_response(request, failure)
            return httpx.Response(200, json=[], headers=base)
        sport = path.split("/sports/")[1].split("/")[0]
        if path.endswith("/events"):
            body = self.listing(sport, priced=False)
            listed = {
                e["id"]: datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
                for e in body
            }
            self.events_calls.append((self.now, sport, listed))
            return httpx.Response(200, json=body, headers={**base, "x-requests-last": "0"})
        if path.endswith("/odds"):
            failure = self.api_failure()
            if failure is not None and failure != CONTRACT:
                return self.failure_response(request, failure)
            markets = request.url.params.get("markets", "")
            cost = len([m for m in markets.split(",") if m])
            if self.used + cost > 500:
                return httpx.Response(429, text="quota", headers=base)
            self.used += cost
            body = self.listing(sport, priced=True)
            priced = {
                (e["id"], datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")))
                for e in body
                if e["bookmakers"]
            }
            self.paid.append(PaidCall(self.now, sport, cost, priced))
            if failure == CONTRACT:
                # Kredyt wydany, treść bezużyteczna — błąd kontraktu.
                self.paid[-1].priced = set()
                return httpx.Response(200, json={"message": "symulacja"}, headers=base)
            headers = {
                "x-requests-used": str(self.used),
                "x-requests-remaining": str(500 - self.used),
                "x-requests-last": str(cost),
            }
            return httpx.Response(200, json=body, headers=headers)
        return httpx.Response(404, text="")


class SimStore:
    """``RawStore`` z błędami zapisu sterowanymi przez świat."""

    def __init__(self, world: World, inner: RawStore) -> None:
        self.world = world
        self.inner = inner
        self.root = inner.root

    def write_raw(self, *args: Any, **kwargs: Any) -> Path:
        call = self.world.paid[-1] if self.world.paid else None
        if self.world.write_fails():
            if call is not None and call.at == self.world.now:
                call.written = False
            raise OSError(errno.ENOSPC, "brak miejsca na dysku (symulacja)")
        path = self.inner.write_raw(*args, **kwargs)
        if call is not None and call.at == self.world.now:
            call.written = True
        return path

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

BASE = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def _round15(t: datetime) -> datetime:
    return t.replace(minute=(t.minute // 15) * 15, second=0, microsecond=0)


def generate(seed: int) -> World:
    rng = random.Random(seed)
    kinds: list[str] = []
    start = BASE + timedelta(days=rng.randrange(0, 60), minutes=rng.randrange(0, 24 * 60, 5))
    gap = rng.random() < 0.1
    if gap:
        kinds.append("dziura")
    horizon_hours = rng.uniform(56, 80) if gap else rng.uniform(4, 26)
    sports = [lg.sport_key for lg in LEAGUES]
    league_set = rng.sample(sports, k=rng.choice((1, 1, 2, 3)))
    matches: list[SimMatch] = []
    n = rng.randint(1, 5)
    for i in range(n):
        sport = rng.choice(league_set)
        if matches and rng.random() < 0.3:
            ko = matches[-1].schedule[0][1]
            sport = matches[-1].sport
            kinds.append("ten-sam-gwizdek")
        else:
            low = horizon_hours - 8 if gap else 1.2
            ko = _round15(start + timedelta(hours=rng.uniform(low, horizon_hours)))
        mode = rng.random()
        if mode < 0.65:
            listed = start
        elif mode < 0.9:
            listed = ko - timedelta(minutes=rng.randrange(60, 300, 1))
            kinds.append("wystawiony-pozno")
        else:
            listed = ko - timedelta(minutes=rng.randrange(10, 59))
            kinds.append("wystawiony-za-pozno")
        listed = max(listed, start)
        schedule = [(listed, ko)]
        if rng.random() < 0.25 and ko - listed > timedelta(minutes=40):
            change_at = listed + (ko - listed) * rng.uniform(0.1, 0.9)
            shift = timedelta(minutes=rng.choice((-1, 1)) * rng.randrange(30, 241, 15))
            new_ko = ko + shift
            if new_ko > change_at + timedelta(minutes=20):
                schedule.append((change_at, new_ko))
                kinds.append("przelozony")
        matches.append(
            SimMatch(
                event_id=f"s{seed}-m{i}",
                sport=sport,
                listed_at=listed,
                schedule=schedule,
                pinnacle=rng.random() > 0.1,
            )
        )
    if rng.random() < 0.5:
        kinds.append("odlegle-mecze")
        for j in range(rng.randint(1, 3)):
            far = _round15(start + timedelta(days=rng.uniform(10, 40)))
            matches.append(
                SimMatch(f"s{seed}-far{j}", rng.choice(league_set), start, [(start, far)], True)
            )
    budget_mode = rng.random()
    if budget_mode < 0.7:
        used0 = rng.randrange(0, 300)
    elif budget_mode < 0.85:
        used0 = rng.randrange(391, 440)
        kinds.append("tryb-oszczedny")
    else:
        used0 = rng.randrange(444, 451)
        kinds.append("budzet-wyczerpany")
    near = [m for m in matches if "far" not in m.event_id]
    end = max(m.kickoff for m in near) + timedelta(hours=2)

    def windows(count: int, low: int, high: int) -> list[tuple[datetime, datetime]]:
        out = []
        for _ in range(count):
            a = start + (end - timedelta(hours=1) - start) * rng.random()
            out.append((a, min(a + timedelta(minutes=rng.randrange(low, high)), end - STEP * 4)))
        return out

    offline = windows(rng.choice((0, 0, 1, 2, 3)), 10, 300)
    if offline:
        kinds.append("przerwa-komputera")
    disk_low = windows(1, 10, 120) if rng.random() < 0.1 else []
    write_fail = windows(1, 5, 60) if rng.random() < 0.1 else []
    if disk_low:
        kinds.append("malo-miejsca")
    if write_fail:
        kinds.append("blad-zapisu")
    api_fail: list[tuple[datetime, datetime, str]] = []
    sports_fail: list[tuple[datetime, datetime, str]] = []
    for target, label in ((api_fail, ""), (sports_fail, "sports-")):
        if rng.random() < 0.3:
            kind = rng.choice((*PROVIDER_FAILURES, *CLIENT_FAILURES, RATE_LIMIT, CONTRACT))
            for a, b in windows(rng.randint(1, 2), 5, 90):
                target.append((a, b, kind))
            if kind in PROVIDER_FAILURES:
                kinds.append(f"{label}blad-dostawcy")
            elif kind == RATE_LIMIT:
                kinds.append(f"{label}limit-429")
            elif kind == CONTRACT:
                kinds.append(f"{label}blad-kontraktu")
            else:
                kinds.append(f"{label}blad-4xx")
    return World(
        seed=seed,
        start=start,
        end=end,
        offset=timedelta(minutes=rng.randrange(0, 5)),
        matches=matches,
        used0=used0,
        offline=offline,
        disk_low=disk_low,
        write_fail=write_fail,
        kinds=sorted(set(kinds)),
        api_fail=api_fail,
        sports_fail=sports_fail,
    )


# ---------------------------------------------------------------------------
# Przebieg i wyrocznia
# ---------------------------------------------------------------------------


def run(world: World, tmp: Path) -> list[str]:
    """Przebieg świata; zwraca listę naruszeń niezmiennika (pusta = OK).

    ``os.fsync`` wyłączony na czas symulacji — to trwałość zapisu na dysku,
    nie logika kolektora, a zjadał 2/3 czasu 500 scenariuszy.
    """
    with mock.patch("valuebet.fsutil.os.fsync", lambda _fd: None):
        return _run(world, tmp)


def run_seed(seed: int) -> tuple[int, list[str], str, int]:
    """Jeden świat w katalogu tymczasowym — jednostka pracy dla puli procesów.

    Czwarty element: liczba meczów wyłączonych przez zawężenie (decyzja
    Pawła 2026-10-04: test ją wypisuje).
    """
    world = generate(seed)
    with tempfile.TemporaryDirectory(prefix=f"vb-sim-{seed}-") as tmp:
        violations = run(world, Path(tmp))
    return seed, violations, describe(world), len(world.excluded)


def observed(world: World, m: SimMatch) -> bool:
    """Czy mecz był poznawalny dla kolektora w TYM świecie.

    Poznawalny = w czasie, gdy ``/events`` go listował, komputer działał bez
    przerwy ≥ 60 min (13 kolejnych przebiegów) — pełny cykl odświeżania
    terminarza ze specyfikacji (decyzja Pawła, pkt 1). Mecz wystawiony i
    zdjęty z listy w czasie przerw jest niepoznawalny: ``/events`` nie podaje
    meczów zakończonych, a ``/scores`` jest płatne; śladem po nim jest luka
    w heartbeacie. Warunek zależy tylko od świata, nie od implementacji —
    ten sam dla kodu sprzed i po naprawie. JEDYNE zawężenie niezmiennika,
    zapisane w FIX_LOG.
    """
    run_ticks = set(world.ticks_run)
    t = world.start + world.offset
    streak = 0
    while t <= world.end:
        if m.listed(t) and t in run_ticks:
            streak += 1
            if streak >= 13:
                return True
        else:
            streak = 0
        t += STEP
    return False


def heartbeat_shows_gap(heartbeat: list[datetime], world: World, m: SimMatch) -> bool:
    """Czy WŁASNY heartbeat kolektora pokazuje lukę w czasie listowania meczu.

    Zawężenie wolno zastosować tylko wtedy, gdy ślad po niepoznawalności
    jest w danych kolektora (decyzja Pawła 2026-10-04): w okresie, gdy
    ``/events`` listował mecz, heartbeat nie ma 13 kolejnych linii co 5 min.
    """
    beats = set(heartbeat)
    t = world.start + world.offset
    streak = 0
    while t <= world.end:
        if m.listed(t) and t in beats:
            streak += 1
            if streak >= 13:
                return False
        else:
            streak = 0
        t += STEP
    return True


def _read_heartbeat(path: Path) -> list[datetime]:
    if not path.exists():
        return []
    return [
        datetime.fromisoformat(json.loads(line)["at"])
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def last_seen_kickoff(world: World, m: SimMatch) -> datetime | None:
    """Ostatni gwizdek tego meczu, jaki ``/events`` pokazał kolektorowi.

    Mecz przełożony w czasie przerwy komputera kolektor raportuje pod
    gwizdkiem, który znał — nowego terminu nigdy nie widział. Prawdziwość
    powodu sprawdzamy i tak wobec PRAWDZIWEGO gwizdka.
    """
    seen = None
    for _, sport, listed in world.events_calls:
        if sport == m.sport and m.event_id in listed:
            seen = listed[m.event_id]
    return seen


def _run(world: World, tmp: Path) -> list[str]:
    store = SimStore(world, RawStore(root=tmp / "raw", manifest=tmp / "manifest.jsonl"))
    client = OddsApiClient(
        http=fake_http(world.handler), settings=OddsApiSettings(api_key="k" * 32)
    )
    collector = build(
        OddsCollector,
        client=client,
        store=store,
        state_root=tmp / "state",
        free_bytes=lambda _path: LOW_DISK if world.disk_is_low() else 10 * 1024**3,
    )
    violations: list[str] = []
    t = world.start + world.offset
    while t <= world.end:
        world.now = t
        world.used_at[t] = world.used
        if not _overlaps(world.offline, t, t + timedelta(seconds=1)):
            world.ticks_run.append(t)
            try:
                collector.run_once(now=t)
            except Exception as exc:  # wyjątek przebiegu to naruszenie
                violations.append(f"run_once({t.isoformat()}) rzucił {type(exc).__name__}: {exc}")
                break
        t += STEP
    missed = _read_missed(tmp / "state" / "closing_missed.jsonl")
    heartbeat = _read_heartbeat(tmp / "state" / "heartbeat.jsonl")
    for m in world.matches:
        if not m.covered or m.kickoff > world.end - timedelta(minutes=30):
            continue
        if not observed(world, m):
            world.excluded.append(m.event_id)
            if not heartbeat_shows_gap(heartbeat, world, m):
                violations.append(
                    f"{m.event_id}: wyłączony przez zawężenie, a heartbeat nie ma luki"
                )
            continue
        problem = _judge(world, m, missed)
        if problem:
            violations.append(f"{m.event_id} KO {m.kickoff.isoformat()}: {problem}")
    return violations


def _read_missed(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _judge(world: World, m: SimMatch, missed: list[dict[str, Any]]) -> str | None:
    ko = m.kickoff
    collected = any(
        ko - CLOSING_SPAN <= call.at <= ko
        and call.written is True
        and (m.event_id, ko) in call.priced
        for call in world.paid
    )
    # Mecz przełożony w czasie przerwy: kolektor raportuje go pod gwizdkiem,
    # który ostatnio widział w /events — nowego terminu nie mógł znać.
    accepted = {ko, last_seen_kickoff(world, m) or ko}
    entries = [
        e
        for e in missed
        if e.get("event_id") == m.event_id
        and any(_same(e.get("kickoff"), k) for k in accepted)
    ]
    if collected:
        return None
    if not entries:
        return "brak zamknięcia i brak wpisu closing_missed"
    last = entries[-1]
    reason = last.get("reason")
    if reason not in REASONS:
        return f"closing_missed z powodem spoza listy: {reason!r}"
    if not _truthful(world, m, reason):
        return f"powód nieprawdziwy w tym świecie: {reason!r}"
    if reason in (REASON_API, REASON_CLIENT, REASON_CONTRACT) and "http_status" not in last:
        return f"wpis {reason!r} bez kodu HTTP"
    if (
        reason in (REASON_API, REASON_CLIENT, REASON_CONTRACT)
        and last.get("collector_gap") is not False
    ):
        return f"wpis {reason!r} z collector_gap={last.get('collector_gap')!r}"
    return None


def _same(raw: object, ko: datetime) -> bool:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")) == ko
    except ValueError:
        return False


def _truthful(world: World, m: SimMatch, reason: str) -> bool:
    ko = m.kickoff
    if reason == REASON_OFFLINE:
        t = world.start + world.offset
        while t < ko:
            if ko - timedelta(minutes=67) <= t and t not in world.ticks_run:
                return True
            t += STEP
        return False
    if reason == REASON_BUDGET:
        league = next(lg for lg in LEAGUES if lg.sport_key == m.sport)
        return _api_failed(world, ko, (RATE_LIMIT,)) or any(
            ko - CLOSING_SPAN <= t < ko and used + league.credits_per_call > BUDGET
            for t, used in world.used_at.items()
        )
    if reason == REASON_NO_PINNACLE:
        return not m.pinnacle
    if reason == REASON_STORAGE:
        return _overlaps(world.disk_low + world.write_fail, ko - CLOSING_SPAN, ko)
    if reason == REASON_API:
        return _api_failed(world, ko, PROVIDER_FAILURES)
    if reason == REASON_CLIENT:
        return _api_failed(world, ko, CLIENT_FAILURES)
    if reason == REASON_CONTRACT:
        return _api_failed(world, ko, (CONTRACT,))
    return False


def _api_failed(world: World, ko: datetime, kinds: tuple[str, ...]) -> bool:
    """Awaria ``/odds`` danego rodzaju w oknie zamknięcia ``[KO-30, KO)``."""
    return any(
        kind in kinds and a < ko and ko - CLOSING_SPAN < b
        for a, b, kind in world.api_fail + world.sports_fail
    )


def describe(world: World) -> str:
    lines = [
        f"ziarno {world.seed}: start {world.start.isoformat()}, koniec {world.end.isoformat()}, "
        f"przesunięcie {world.offset}, used0 {world.used0}, rodzaje {world.kinds}",
    ]
    for m in world.matches:
        lines.append(
            f"  {m.event_id} {m.sport} listowany {m.listed_at.isoformat()} "
            f"terminarz {[(a.isoformat(), b.isoformat()) for a, b in m.schedule]} "
            f"pinnacle={m.pinnacle} objęty={m.covered}"
        )
    for name in ("offline", "disk_low", "write_fail"):
        spans = getattr(world, name)
        if spans:
            lines.append(f"  {name}: {[(a.isoformat(), b.isoformat()) for a, b in spans]}")
    lines.append(f"  płatne wywołania: {len(world.paid)}, used na końcu {world.used}")
    return "\n".join(lines)
