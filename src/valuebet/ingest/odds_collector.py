"""Kolektor The Odds API — S1 z ROADMAP §6, harmonogram z COLLECTOR_PLAN §3.3.

Zasada nadrzędna: **pobieraj głupio, parsuj później**
------------------------------------------------------
Surowa odpowiedź ląduje na dysku w całości, zanim cokolwiek z niej
wyciągniemy. Dziś nie wiadomo, których pól będziemy potrzebować za rok, a
**ponownie pobrać przeszłości się nie da**. Parsowanie jest odwracalne,
utrata danych nie.

Dlatego ten moduł nie ma parsera kursów. Ma tylko: zdecydować czy coś się
należy, pobrać, zapisać surowo, odnotować bicie serca.

Kto decyduje o wywołaniu
------------------------
Task Scheduler odpala kolektor co 5 minut, a kolektor sam sprawdza, czy
któraś kotwica jest należna. Zwykle nie jest i proces kończy się szybko.
Odwrotny układ — harmonogram w Windows wiedzący o terminarzu Ekstraklasy —
wymagałby przepisywania zadania co kolejkę.

Terminarz wyłącznie z ``/events``
---------------------------------
Bezpłatne ``/events`` (dokumentacja v4: „does not count against the usage
quota”) odświeżane BEZWARUNKOWO, gdy ostatnie udane odświeżenie ligi jest
starsze niż 60 min. Jedyne źródło terminarza i mianownika pokrycia
zamknięć; płatne odpowiedzi go nie zasilają. Wcześniej terminarz żył z
odpowiedzi płatnych wywołań — i trzy rundy audytu z rzędu (F0b-01,
F0c-02, F0d-01) kolektor potrafił zamilknąć, gdy nic nie było należne
(decyzja Pawła 2026-10-03). Po gwizdku każdy mecz z terminarza kończy się
zamknięciem albo wpisem ``closing_missed`` z powodem z ``MISSED_REASONS``.

Kotwice (S1)
------------
- **Ekstraklasa**: zamknięcie główne, dwa rynki (``h2h``, ``totals``).
  Kotwica T-24h usunięta (decyzja Pawła 2026-10-04): dublowała poranne
  migawki decyzyjne, a oś ``bet_lead_time`` to migawki decyzyjne (ok.
  4-40 h do gwizdka) kontra zamknięcie (COLLECTOR_PLAN §3.3).
- **Premier League, Bundesliga**: zamknięcie główne i zapasowe, dwa rynki
  (``h2h``, ``totals``). Są tu dla wolumenu i dla kalibracji totali na
  lidze o głębokim rynku — nie zamierzamy w nich grać.
- **Wszystkie trzy**: migawka decyzyjna raz dziennie, 08:30 Warszawa.

Mecze z tym samym gwizdkiem obsługuje **jedno** wywołanie: ``/odds`` zwraca
wszystkie nadchodzące zdarzenia ligi naraz. Kluczem kotwicy jest zdarzenie
(gwizdek), nie przedział godzinowy (FSA #0 F-13).

Budżet
------
450 kredytów na miesiąc z 500 (50 zapasu); dostawca liczy kredyt za rynek,
każda liga ma dziś dwa (``h2h``, ``totals``), więc 2 kredyty za ``/odds``.
``/events`` jest bezpłatne. Plan: ``scripts/odds_budget.py`` (symulacja
prawdziwego ``due_calls``). Źródłem prawdy jest licznik z nagłówków odpowiedzi,
nie plik lokalny — lokalny rozjeżdża się po każdym nieudanym przebiegu.

Luki są daną
------------
Każdy przebieg dopisuje linię do heartbeatu, **także gdy nic się nie
należało**. Bez tego nie da się odróżnić „nie było czego zbierać" od
„komputer spał" — a to pierwsza rzecz, o którą zapytamy, gdy w danych
pojawi się dziura.
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from valuebet.closing import CLOSING_TARGET, CLOSING_TOLERANCE
from valuebet.fsutil import write_atomic
from valuebet.ingest.odds_api import (
    BudgetExhaustedError,
    BudgetSkipError,
    OddsApiClient,
    OddsApiError,
    UsageCounters,
    UsageGuard,
)
from valuebet.ingest.raw_store import RawStore

__all__ = [
    "CLOSING",
    "CLOSING_BACKUP",
    "DECISION_MARKETS",
    "EVENTS_REFRESH",
    "KICKOFFS_SEEN_DAYS",
    "LEAGUES",
    "MIN_FREE_BYTES",
    "MISSED_REASONS",
    "Anchor",
    "LeagueConfig",
    "OddsCollector",
    "PlannedCall",
    "api_failure_reason",
    "closing_coverage",
    "decision_due",
    "decision_window_utc",
    "due_calls",
    "has_pinnacle_closing",
    "known_kickoffs",
    "migrate_done_keys",
    "migrate_state",
    "prune_history",
    "record_events",
    "schedule_empty",
]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Anchor:
    """Kotwica czasowa: ile przed gwizdkiem i jak szerokie okno trafienia.

    Okno musi być szersze niż krok harmonogramu (5 min, zadanie
    ``valuebet-odds``), inaczej pojedyncze opóźnienie Windows gubi kotwicę
    bezpowrotnie.
    """

    name: str
    before: timedelta
    window: timedelta = timedelta(minutes=20)

    def is_due(self, *, now: datetime, kickoff: datetime) -> bool:
        """Czy kotwica jest należna. **Nigdy po gwizdku.**

        Okno jest przycinane do momentu rozpoczęcia meczu: zamknięcie
        pobrane po pierwszym gwizdku nie jest zamknięciem, tylko kursem
        live, a live świadomie nie zbieramy.
        """
        target = kickoff - self.before
        end = min(target + self.window, kickoff)
        return target <= now < end


#: Zamknięcie GŁÓWNE: pierwszy przebieg w ``[KO - 7 min, KO)`` (FSA #0 F-13).
#: Krok harmonogramu 5 min, więc okno 7 min ma zawsze przebieg, gdy komputer
#: nie śpi. Poprzednie okno 25 min przy kroku 15 min gubiło zamknięcie przy
#: każdej zmierzonej luce ≥ 30 min (heartbeat 2026-10-01: 31.6% tyknięć
#: przegapionych).
CLOSING = Anchor("closing", CLOSING_TARGET, window=CLOSING_TARGET)
#: Zamknięcie ZAPASOWE: pierwszy przebieg w ``[KO - 30, KO - 7)`` — nadal w
#: tolerancji CLV (``closing.CLOSING_TOLERANCE``). Tylko poza trybem
#: oszczędnym budżetu (F-15); CLV bierze najpóźniejszą migawkę ≤ KO.
CLOSING_BACKUP = Anchor(
    "closing_backup", CLOSING_TOLERANCE, window=CLOSING_TOLERANCE - CLOSING_TARGET
)
#: Strefa, w której myśli człowiek podejmujący decyzję.
WARSAW = ZoneInfo("Europe/Warsaw")

#: Migawka decyzyjna (TOR_S_PLAN §2): raz dziennie, o stałej godzinie
#: ŚCIENNEJ, nie względem gwizdka.
#:
#: Powód jest po stronie człowieka, nie danych. Zamknięcie ~25 min przed
#: meczem jest bezużyteczne do ręcznej decyzji — trzeba zdążyć porównać
#: kurs u bukmachera i kliknąć. Migawka rano daje progi na cały dzień.
#:
#: Godzina ścienna znaczy, że liczymy ją w Europe/Warsaw i przeliczamy na
#: UTC przy każdym sprawdzeniu — inaczej po zmianie czasu migawka
#: przesunęłaby się o godzinę względem dnia człowieka.
DECISION_HOUR_WARSAW = 8
DECISION_MINUTE_WARSAW = 30
DECISION_WINDOW = timedelta(minutes=45)

#: Ile naprzód patrzy migawka decyzyjna: liga gra dziś albo nazajutrz.
DECISION_HORIZON = timedelta(hours=48)

#: Rynki migawki decyzyjnej. Bez ``spreads`` — do progów 1X2 i totali
#: wystarczą dwa, a trzeci kosztowałby 50% więcej.
DECISION_MARKETS: tuple[str, ...] = ("h2h", "totals")

#: Kotwica pozorna — migawka decyzyjna nie liczy się od gwizdka, więc
#: ``before`` jest zerowe, a należność rozstrzyga ``decision_due``.
DECISION = Anchor("decision", timedelta(0), window=DECISION_WINDOW)


@dataclass(frozen=True)
class LeagueConfig:
    sport_key: str
    markets: tuple[str, ...]
    anchors: tuple[Anchor, ...]
    label: str

    @property
    def credits_per_call(self) -> int:
        """Dostawca liczy jeden kredyt za rynek."""
        return len(self.markets)


#: Zakres S1. Kotwice meczowe to wyłącznie zamknięcia; cenę wejścia daje
#: migawka decyzyjna (wspólna dla lig, ``decision_due``).
LEAGUES: tuple[LeagueConfig, ...] = (
    LeagueConfig(
        sport_key="soccer_poland_ekstraklasa",
        # Bez ``spreads`` i bez zamknięcia zapasowego — budżet 450 (FSA #0
        # F-13): kotwice po gwizdku dały 624 kredyty/mies.; ustępstwa w
        # kolejności z TOR_S_PLAN §2 (najpierw spreads Ekstraklasy) i
        # FSA0_NAPRAWY §3 F-13 (zapasowe tylko PL i Bundesliga) → 431.
        # Bez T-24h — dubluje migawki decyzyjne (decyzja Pawła 2026-10-04,
        # F0e-01: plan ~456 > 450).
        markets=("h2h", "totals"),
        anchors=(CLOSING,),
        label="ekstraklasa",
    ),
    LeagueConfig(
        sport_key="soccer_epl",
        markets=("h2h", "totals"),
        anchors=(CLOSING_BACKUP, CLOSING),
        label="premier_league",
    ),
    LeagueConfig(
        sport_key="soccer_germany_bundesliga",
        markets=("h2h", "totals"),
        anchors=(CLOSING_BACKUP, CLOSING),
        label="bundesliga",
    ),
)


def decision_window_utc(*, now: datetime) -> tuple[datetime, datetime]:
    """Okno migawki decyzyjnej dla doby warszawskiej, w której jest ``now``.

    Liczone od godziny ściennej, więc przy zmianie czasu przesuwa się razem
    z zegarem człowieka, a nie względem niego.
    """
    local = now.astimezone(WARSAW)
    start_local = local.replace(
        hour=DECISION_HOUR_WARSAW,
        minute=DECISION_MINUTE_WARSAW,
        second=0,
        microsecond=0,
    )
    start = start_local.astimezone(UTC)
    return start, start + DECISION_WINDOW


def decision_due(
    *, now: datetime, kickoffs: list[datetime], done: set[str], label: str
) -> bool:
    """Czy migawka decyzyjna jest należna: jesteśmy w oknie i liga gra."""
    start, end = decision_window_utc(now=now)
    if not (start <= now < end):
        return False
    local_day = now.astimezone(WARSAW).date().isoformat()
    if f"{label}|decision|{local_day}" in done:
        return False
    return any(now <= k < now + DECISION_HORIZON for k in kickoffs)


@dataclass(frozen=True)
class PlannedCall:
    """Jedno należne wywołanie: liga, kotwica, zdarzenie (gwizdek).

    Klucz kotwicy to **zdarzenie**, nie przedział godzinowy (FSA #0 F-13):
    mecze o tej samej godzinie gwizdka dzielą jedno wywołanie, mecz o 19:30
    ma własne — przy oknie 7 min nie da się złapać dwóch gwizdków jednym
    zapytaniem. ``slot`` = ``reference`` = gwizdek.
    """

    league: LeagueConfig
    anchor: Anchor
    slot: datetime
    reference: datetime
    #: Nadpisanie rynków. Migawka decyzyjna bierze dwa, nie trzy.
    markets: tuple[str, ...] | None = None

    @property
    def effective_markets(self) -> tuple[str, ...]:
        return self.markets if self.markets is not None else self.league.markets

    @property
    def credits(self) -> int:
        return len(self.effective_markets)

    @property
    def key(self) -> str:
        if self.anchor.name == "decision":
            # Klucz dzienny: jedna migawka decyzyjna na ligę na dobę.
            return f"{self.league.label}|decision|{self.slot.date().isoformat()}"
        return f"{self.league.label}|{self.anchor.name}|{self.reference.isoformat()}"


def _slot_of(kickoff: datetime) -> datetime:
    """Godzina gwizdka — używana tylko do migracji starych kluczy i kalkulatora."""
    return kickoff.replace(minute=0, second=0, microsecond=0)


def migrate_done_keys(done: set[str], *, kickoffs: dict[str, list[datetime]]) -> set[str]:
    """Stare klucze ``liga|kotwica|<godzina slotu>`` → klucze po gwizdku.

    Kotwica zebrana dla slotu obejmowała wszystkie mecze z tej godziny, więc
    każdy z nich dostaje klucz „zrobione” — nic nie jest pobierane drugi raz.
    Idempotentne: klucz, którego czas jest gwizdkiem, zostaje bez zmian.
    """
    by_label = {league.label: league.sport_key for league in LEAGUES}
    out: set[str] = set()
    for key in done:
        label, _, rest = key.partition("|")
        anchor, _, stamp = rest.partition("|")
        sport = by_label.get(label)
        if anchor in ("decision", "schedule_probe", "") or sport is None:
            out.add(key)
            continue
        slot = datetime.fromisoformat(stamp)
        games = [k for k in kickoffs.get(sport, []) if slot <= k < slot + timedelta(hours=1)]
        if not games or slot in games:
            out.add(key)
        out.update(f"{label}|{anchor}|{k.isoformat()}" for k in games)
    return out


def due_calls(
    *,
    now: datetime,
    kickoffs: dict[str, list[datetime]],
    done: set[str],
    leagues: tuple[LeagueConfig, ...] = LEAGUES,
) -> list[PlannedCall]:
    """Czyste planowanie: co jest należne teraz i jeszcze nie zrobione.

    Funkcja bez efektów ubocznych, żeby dało się ją przetestować na
    sztucznym zegarze zamiast czekać do soboty.
    """
    planned: list[PlannedCall] = []
    for league in leagues:
        events = sorted(set(kickoffs.get(league.sport_key, [])))
        for anchor in league.anchors:
            for kickoff in events:
                call = PlannedCall(league, anchor, kickoff, kickoff)
                if call.key in done:
                    continue
                if anchor.is_due(now=now, kickoff=kickoff):
                    planned.append(call)
        if decision_due(
            now=now, kickoffs=kickoffs.get(league.sport_key, []), done=done, label=league.label
        ):
            local_day = now.astimezone(WARSAW).date()
            planned.append(
                PlannedCall(
                    league=league,
                    anchor=DECISION,
                    slot=datetime.combine(local_day, time(0), tzinfo=UTC),
                    reference=now,
                    markets=DECISION_MARKETS,
                )
            )
    return planned


#: Podkatalog surowych migawek w ``data/raw`` — reguła 12, zapis wyłącznie
#: przez ``RawStore`` (manifest sum kontrolnych, FSA #0 F-12).
RAW_SUBDIR = "odds/odds_api"
#: Stan kolektora i heartbeat. **Nie** w ``data/raw/``: ``state.json`` jest
#: nadpisywany przy każdym przebiegu, a heartbeat rośnie — oba zmieniają
#: hash, więc w raw łamałyby regułę 12 i manifest (FSA #0 F-14).
STATE_ROOT = Path("data/state/odds_api")
#: Jak długo trzymamy w stanie mecze już rozegrane (``events_seen``) — z
#: zapasem ponad tygodniową miarę pokrycia zamknięć (F0b-01).
KICKOFFS_SEEN_DAYS = 35
#: Identyfikator zastępczy z rundy 0c (terminarz z godzin) — usuwany przy migracji.
LEGACY_PREFIX = "legacy:"
#: Terminarz z bezpłatnego ``/events`` odświeżany, gdy ostatnie udane
#: odświeżenie jest starsze niż tyle (decyzja Pawła 2026-10-03, F0d-01).
EVENTS_REFRESH = timedelta(minutes=60)
#: Minimum wolnego miejsca przed płatnym wywołaniem (F0d-05): kredyt wydany
#: na odpowiedź, której nie da się zapisać, przepada.
MIN_FREE_BYTES = 200 * 1024 * 1024
#: Kotwice, których odpowiedź jest zamknięciem (``[KO-30, KO)``).
CLOSING_ANCHORS = frozenset({"closing", "closing_backup"})
#: Zamknięta lista powodów w ``closing_missed`` (decyzja Pawła 2026-10-03, pkt 2)
#: plus dwa zaakceptowane warunkowo (2026-10-04 pkt 2, 2026-10-07):
#: „błąd API dostawcy” wyłącznie dla 5xx, timeoutu i zerwanego połączenia;
#: „błąd kolektora (HTTP 4xx)” dla 4xx poza 429 (429 → budżet). Siódmy —
#: „błąd kontraktu API” (HTTP 200 ze złą treścią; decyzja Architekta 2026-10-07).
REASON_OFFLINE = "komputer nie działał"
REASON_BUDGET = "budżet > 450"
REASON_NO_PINNACLE = "brak rynku Pinnacle"
REASON_STORAGE = "brak miejsca / błąd zapisu"
REASON_API = "błąd API dostawcy"
REASON_CLIENT = "błąd kolektora (HTTP 4xx)"
REASON_CONTRACT = "błąd kontraktu API"
MISSED_REASONS: tuple[str, ...] = (
    REASON_OFFLINE,
    REASON_BUDGET,
    REASON_NO_PINNACLE,
    REASON_STORAGE,
    REASON_API,
    REASON_CLIENT,
    REASON_CONTRACT,
)
_HTTP_TOO_MANY = 429
_HTTP_CLIENT_ERRORS = range(400, 500)


def api_failure_reason(exc: OddsApiError) -> str:
    """Powód ``closing_missed`` z rodzaju błędu (decyzje Pawła 2026-10-04, 2026-10-07).

    429 → budżet; pozostałe 4xx → błąd kolektora; 5xx, timeout, zerwane
    połączenie → błąd API dostawcy.
    """
    if exc.error_kind == "contract":
        return REASON_CONTRACT
    status = exc.http_status
    if status == _HTTP_TOO_MANY:
        return REASON_BUDGET
    if status is not None and status in _HTTP_CLIENT_ERRORS:
        return REASON_CLIENT
    return REASON_API


@dataclass
class OddsCollector:
    """Jeden przebieg: terminarz z ``/events``, kotwice, zapis surowy, rozliczenie zamknięć."""

    client: OddsApiClient
    store: RawStore = field(default_factory=RawStore)
    state_root: Path = STATE_ROOT
    #: Wolne bajty na dysku magazynu raw — sprawdzane przed każdym płatnym
    #: wywołaniem (F0d-05). Wstrzykiwalne dla testów; domyślnie prawdziwy dysk.
    free_bytes: Callable[[Path], int] = field(default=lambda path: _disk_free(path))
    state_file: Path = field(init=False)
    heartbeat_file: Path = field(init=False)
    usage_file: Path = field(init=False)
    missed_file: Path = field(init=False)

    def __post_init__(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_root / "state.json"
        self.heartbeat_file = self.state_root / "heartbeat.jsonl"
        self.usage_file = self.state_root / "usage.jsonl"
        self.missed_file = self.state_root / "closing_missed.jsonl"

    @property
    def root(self) -> Path:
        """Katalog surowych migawek kolektora w raw."""
        return self.store.root / RAW_SUBDIR

    # -- stan -------------------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {"done": [], "events_seen": {}, "last_usage": None}
        loaded = json.loads(self.state_file.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise OddsApiError(
                f"plik stanu {self.state_file} nie jest obiektem JSON"
            )
        return loaded

    def _save_state(self, state: dict[str, Any]) -> None:
        """Atomowo: przerwany zapis nie może zostawić uciętego ``done``."""
        write_atomic(
            self.state_file,
            json.dumps(state, indent=2, ensure_ascii=False, default=str).encode(
                "utf-8"
            ),
        )

    def _heartbeat(self, entry: dict[str, Any]) -> None:
        """Dopisuje linię ZAWSZE, także gdy nic się nie należało.

        Bez tego luka w danych jest nieodróżnialna od spokojnego dnia.
        """
        with self.heartbeat_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    # -- zapis surowy -----------------------------------------------------

    def _write_raw(self, call: PlannedCall, response: Any, *, now: datetime) -> Path:
        """Zapis do ``data/raw/`` przez ``RawStore`` — append-only z manifestem.

        Nazwę nadaje magazyn (kotwica, znacznik z mikrosekundami, prefiks
        hasha). Kolizja oznacza powtórzony zapis tych samych bajtów w tej
        samej chwili; wtedy podnosimy wyjątek zamiast zamazać plik (reguła 12).
        """
        payload = {
            # Reguła 14: każdy zapisany zbiór ma ingested_at i source.
            "ingested_at": now.isoformat(),
            "source": "the-odds-api-v4",
            "sport_key": call.league.sport_key,
            "anchor": call.anchor.name,
            "slot": call.slot.isoformat(),
            "anchor_reference": call.reference.isoformat(),
            "markets": list(call.effective_markets),
            "requested_url": response.requested_url,
            "credits_spent": call.credits,
            "usage_remaining": response.usage.remaining,
            "events": response.events,
        }
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        try:
            return self.store.write_raw(
                f"{RAW_SUBDIR}/{call.league.label}",
                call.anchor.name,
                ".json",
                data,
                now=now,
                recorded_by="odds_collector",
            )
        except FileExistsError as exc:
            raise OddsApiError(f"plik surowy już istnieje, nie nadpisuję: {exc}") from None

    # -- licznik ----------------------------------------------------------

    def _usage_line(self, *, now: datetime, endpoint: str, usage: UsageCounters) -> None:
        """Nagłówki dostawcy po KAŻDYM wywołaniu — prawda o budżecie (F-15/F-16)."""
        line = {
            "at": now.isoformat(),
            "endpoint": endpoint,
            "used": usage.used,
            "remaining": usage.remaining,
            "last": usage.last,
        }
        with self.usage_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")

    def _fresh_guard(
        self, *, now: datetime, entry: dict[str, Any]
    ) -> tuple[UsageGuard, OddsApiError | None]:
        """Licznik z bezpłatnego ``/sports`` — przed pierwszym płatnym wywołaniem.

        Licznik nieznany (``used = None``) blokuje płatne wywołania w
        ``UsageGuard``. Drugi element — błąd ``/sports``, z którego wpis
        ``closing_missed`` bierze kod HTTP i powód (decyzja Architekta
        2026-10-07); brak nagłówka licznika w odpowiedzi 200 = błąd kontraktu.
        """
        try:
            usage = self.client.refresh_usage()
        except OddsApiError as exc:
            entry["errors"].append(f"licznik zużycia: {exc}")
            return UsageGuard(used=None), exc
        self._usage_line(now=now, endpoint="/sports", usage=usage)
        entry["usage_used"] = usage.used
        entry["usage_remaining"] = usage.remaining
        if usage.used is None:
            missing = OddsApiError(
                "/sports: odpowiedź 200 bez nagłówka x-requests-used",
                http_status=200,
                error_kind="contract",
            )
            entry["errors"].append(f"licznik zużycia: {missing}")
            return UsageGuard(used=None), missing
        return UsageGuard(used=usage.used), None

    # -- terminarz z /events ------------------------------------------------

    def _refresh_events(
        self, state: dict[str, Any], *, now: datetime, entry: dict[str, Any], force: bool
    ) -> None:
        """Terminarz każdej ligi z ``/events``, gdy ostatnie udane odświeżenie ≥ 60 min.

        BEZWARUNKOWO — bez warunków typu „brak przyszłego meczu” (decyzja
        Pawła 2026-10-03; F0d-01: każda heurystyka zostawiała świat, w którym
        kolektor milkł). Budżet i tryb oszczędny ``/events`` nie dotyczą.
        Koszt sprawdzany z nagłówka: ``x-requests-last > 0`` → ``/events``
        wyłączone do ręcznej decyzji i głośny błąd w każdym heartbeacie.
        """
        if state.get("events_cost_alarm"):
            entry["errors"].append(
                f"/events wyłączone: {state['events_cost_alarm']} — decyzja człowieka"
            )
            return
        refreshed: dict[str, str] = state.setdefault("events_refreshed", {})
        for league in LEAGUES:
            last = refreshed.get(league.sport_key)
            if not force and last is not None and now - _utc(last) < EVENTS_REFRESH:
                continue
            try:
                response = self.client.fetch_events(sport_key=league.sport_key)
            except OddsApiError as exc:
                entry["errors"].append(f"/events {league.label}: {exc}")
                continue
            self._usage_line(now=now, endpoint=f"/events {league.label}", usage=response.usage)
            if response.usage.last not in (None, 0):
                state["events_cost_alarm"] = (
                    f"{now.isoformat()} /events {league.label} x-requests-last="
                    f"{response.usage.last}"
                )
                entry["errors"].append(f"/events kosztowało kredyty: {state['events_cost_alarm']}")
                return
            record_events(state, sport_key=league.sport_key, events=response.events)
            refreshed[league.sport_key] = now.isoformat()
            entry["events_refreshed"].append(league.label)

    def refresh_events(self, *, now: datetime) -> dict[str, Any]:
        """Ręczne odświeżenie terminarza (``collect_odds.py --refresh``) — bezpłatne."""
        state = self._load_state()
        migrate_state(state)
        entry: dict[str, Any] = {"at": now.isoformat(), "events_refreshed": [], "errors": []}
        self._refresh_events(state, now=now, entry=entry, force=True)
        prune_history(state, now=now)
        self._save_state(state)
        self._heartbeat(entry)
        return entry

    # -- zamknięcia ---------------------------------------------------------

    def _closing_failed(
        self,
        state: dict[str, Any],
        call: PlannedCall,
        reason: str,
        error: OddsApiError | None = None,
    ) -> None:
        """Powód porażki dla meczów tego gwizdka — do ``closing_missed`` po gwizdku.

        Przy błędzie HTTP obok powodu zapisywany jest kod odpowiedzi i rodzaj
        awarii transportu (``closing_failure_http``) — trafiają do wpisu.
        """
        sport = call.league.sport_key
        failures = state.setdefault("closing_failures", {}).setdefault(sport, {})
        details = state.setdefault("closing_failure_http", {}).setdefault(sport, {})
        for event_id, kickoff in state.get("events_seen", {}).get(sport, {}).items():
            if _utc(kickoff) == call.reference:
                key = f"{event_id}|{call.reference.isoformat()}"
                failures[key] = reason
                if error is not None:
                    details[key] = {
                        "reason": reason,
                        "http_status": error.http_status,
                        "error_kind": error.error_kind,
                    }
                else:
                    details.pop(key, None)

    def _closing_collected(
        self, state: dict[str, Any], call: PlannedCall, events: list[dict[str, Any]]
    ) -> None:
        """Zebrane = odpowiedź zawiera mecz TEGO gwizdka z kompletem h2h Pinnacle.

        Klucz (id, gwizdek) — mecz przełożony po zebraniu nie dziedziczy
        „zebrane” na nowy termin (F0d-03). Mecz z terminarza tego gwizdka,
        którego w odpowiedzi nie ma albo nie ma przy nim Pinnacle → powód
        „brak rynku Pinnacle”, osobno od luk kolektora.
        """
        sport = call.league.sport_key
        ref = call.reference.isoformat()
        closed = state.setdefault("closing_events", {}).setdefault(sport, {})
        priced = {
            str(ev["id"])
            for ev in events
            if ev.get("id")
            and ev.get("commence_time")
            and _utc(ev["commence_time"]) == call.reference
            and has_pinnacle_closing(ev)
        }
        for event_id in priced:
            closed[f"{event_id}|{ref}"] = ref
        moved = {
            str(ev["id"])
            for ev in events
            if ev.get("id")
            and ev.get("commence_time")
            and _utc(ev["commence_time"]) != call.reference
        }
        failures = state.setdefault("closing_failures", {}).setdefault(sport, {})
        for event_id, kickoff in state.get("events_seen", {}).get(sport, {}).items():
            key = f"{event_id}|{ref}"
            if _utc(kickoff) != call.reference or key in closed:
                continue
            if event_id in moved:
                # Mecz jest w odpowiedzi pod innym gwizdkiem — przełożony, a
                # terminarz nieaktualny. Nie „brak rynku Pinnacle” (to byłaby
                # nieprawda); terminarz odświeżamy z /events w następnym
                # przebiegu, płatna odpowiedź go nie zasila.
                state.setdefault("events_refreshed", {}).pop(sport, None)
                continue
            failures[key] = REASON_NO_PINNACLE

    def _report_missed(self, state: dict[str, Any], *, now: datetime) -> None:
        """Po gwizdku: każdy niezebrany mecz → ``closing_missed`` z powodem, raz.

        Powód z zamkniętej listy: zapisany przy próbie (budżet, brak rynku
        Pinnacle, brak miejsca / błąd zapisu, błąd API) albo — gdy żadnej
        próby nie było — „komputer nie działał”: terminarz z ``/events`` jest
        odświeżany co ≤ 60 min, więc mecz listowany ≥ 60 min przed gwizdkiem
        bez próby zamknięcia oznacza przebiegi, które się nie odbyły.
        """
        reported = set(state.get("closing_missed", []))
        closed_all = state.get("closing_events", {})
        failures_all = state.get("closing_failures", {})
        details_all = state.get("closing_failure_http", {})
        for league in LEAGUES:
            sport = league.sport_key
            closed = closed_all.get(sport, {})
            failures = failures_all.get(sport, {})
            for event_id, kickoff in state.get("events_seen", {}).get(sport, {}).items():
                ko = _utc(kickoff)
                key = f"{event_id}|{ko.isoformat()}"
                if ko > now or key in closed or key in reported:
                    continue
                reason = failures.get(key, REASON_OFFLINE)
                detail = details_all.get(sport, {}).get(key, {})
                if detail.get("reason") != reason:
                    detail = {}
                line = {
                    "at": now.isoformat(),
                    "league": league.label,
                    "event_id": event_id,
                    "kickoff": ko.isoformat(),
                    "reason": reason,
                    "collector_gap": reason == REASON_OFFLINE,
                    "http_status": detail.get("http_status"),
                    "error_kind": detail.get("error_kind"),
                }
                with self.missed_file.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(line, ensure_ascii=False) + "\n")
                reported.add(key)
        state["closing_missed"] = sorted(reported)

    # -- przebieg ---------------------------------------------------------

    def run_once(self, *, now: datetime) -> dict[str, Any]:
        state = self._load_state()
        migrate_state(state)
        entry: dict[str, Any] = {
            "at": now.isoformat(),
            "planned": [],
            "fetched": [],
            "budget_skip": [],
            "errors": [],
            "events_refreshed": [],
            "usage_remaining": (state.get("last_usage") or {}).get("remaining"),
        }
        self._refresh_events(state, now=now, entry=entry, force=False)
        kickoffs = known_kickoffs(state)
        done = set(state.get("done", []))
        if not state.get("done_keys_migrated"):
            # Jednorazowo (F-13): wołana przy KAŻDYM przebiegu traktowała każdy
            # klucz jak stary klucz godzinowy — zamknięcie meczu o 17:15
            # oznaczało jako zrobione zamknięcie meczu o 18:00 (FSA #0e,
            # znalezione testem niezmiennika, ziarno 2).
            done = migrate_done_keys(done, kickoffs=kickoffs)
            state["done_keys_migrated"] = True
        planned = due_calls(now=now, kickoffs=kickoffs, done=done)
        entry["planned"] = [c.key for c in planned]
        entry["schedule_empty"] = schedule_empty(now=now, kickoffs=kickoffs)

        usage: UsageCounters | None = None
        guard, guard_error = (
            self._fresh_guard(now=now, entry=entry) if planned else (UsageGuard(used=None), None)
        )
        for call in planned:
            is_closing = call.anchor.name in CLOSING_ANCHORS
            free = self.free_bytes(self.store.root)
            if free < MIN_FREE_BYTES:
                entry["errors"].append(
                    f"{call.key}: wolne miejsce {free // (1024 * 1024)} MB < "
                    f"{MIN_FREE_BYTES // (1024 * 1024)} MB — płatne wywołanie pominięte"
                )
                if is_closing:
                    self._closing_failed(state, call, REASON_STORAGE)
                continue
            try:
                response = self.client.fetch_odds(
                    sport_key=call.league.sport_key,
                    markets=call.effective_markets,
                    usage_guard=guard,
                    closing=call.anchor.name == CLOSING.name,
                )
            except BudgetExhaustedError as exc:
                entry["budget_skip"].append(f"{call.key}: {exc}")
                log.warning("budżet: pomijam %s — %s", call.key, exc)
                if is_closing:
                    self._closing_failed(state, call, REASON_BUDGET)
                continue
            except BudgetSkipError as exc:
                # Tryb oszczędny (zapasowe zamknięcie, decyzja) albo
                # nieznany licznik. Zamknięcie główne w trybie oszczędnym idzie.
                entry["budget_skip"].append(f"{call.key}: {exc}")
                log.warning("budżet: pomijam %s — %s", call.key, exc)
                if is_closing and guard.used is None:
                    # Nieznany licznik: płatne wywołanie NIE poszło (UsageGuard);
                    # powód i kod HTTP z błędu /sports.
                    if guard_error is not None:
                        self._closing_failed(
                            state, call, api_failure_reason(guard_error), guard_error
                        )
                    else:
                        self._closing_failed(state, call, REASON_API)
                continue
            except OddsApiError as exc:
                # Heartbeat zapisuje KAŻDY błąd; wpis closing_missed jest
                # dodatkiem, nie zamiennikiem (decyzja Pawła 2026-10-07).
                entry["errors"].append(f"{call.key}: {exc}")
                log.warning("wywołanie %s nie powiodło się: %s", call.key, exc)
                if is_closing:
                    self._closing_failed(state, call, api_failure_reason(exc), exc)
                continue
            usage = response.usage
            self._usage_line(now=now, endpoint=f"/odds {call.key}", usage=usage)
            guard = UsageGuard(used=usage.used)
            try:
                self._write_raw(call, response, now=now)
            except (OddsApiError, OSError) as exc:
                # Kredyt już wydany, ale pliku nie nadpisujemy (reguła 12).
                entry["errors"].append(f"{call.key}: zapis — {exc}")
                log.warning("nie zapisano surowej odpowiedzi %s: %s", call.key, exc)
                if is_closing:
                    self._closing_failed(state, call, REASON_STORAGE)
                continue
            done.add(call.key)
            entry["fetched"].append(call.key)
            entry["usage_remaining"] = usage.remaining
            # Odpowiedź płatna NIE zasila terminarza (decyzja 2026-10-03):
            # jedynym źródłem terminarza i mianownika pokrycia jest /events.
            if is_closing:
                self._closing_collected(state, call, response.events)

        if not planned:
            entry["note"] = "nic nienależne"
        self._report_missed(state, now=now)
        state["done"] = sorted(done)
        if usage is not None:
            state["last_usage"] = {"remaining": usage.remaining, "used": usage.used}
        prune_history(state, now=now)
        self._save_state(state)
        self._heartbeat(entry)
        return entry


def _disk_free(path: Path) -> int:
    """Wolne bajty na dysku najbliższego istniejącego przodka ``path``."""
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def _utc(raw: object) -> datetime:
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)


def has_pinnacle_closing(event: dict[str, Any]) -> bool:
    """Czy zdarzenie ma komplet h2h Pinnacle (trzy wyniki, reguła 17).

    Bez tego zapis odpowiedzi nie jest zamknięciem — CLV i tak nie powstanie
    (brak ``p_close``), ale miara pokrycia liczyła je jako zebrane (F0c-04).
    """
    for book in event.get("bookmakers") or []:
        if book.get("key") != "pinnacle":
            continue
        for market in book.get("markets") or []:
            outcomes = market.get("outcomes") or []
            prices = [o.get("price") for o in outcomes]
            if market.get("key") == "h2h" and len(outcomes) >= 3 and all(
                isinstance(v, int | float) and v > 1.0 for v in prices
            ):
                return True
    return False


def migrate_state(state: dict[str, Any]) -> None:
    """Stan sprzed rundy 0e → terminarz wyłącznie z ``/events``.

    Usuwa terminarz zasilany płatnymi odpowiedziami (``kickoffs``,
    ``kickoffs_seen``, wpisy ``legacy:``) — pierwsze odświeżenie ``/events``
    i tak odbuduje go z jedynego źródła. Prawdziwe identyfikatory zdarzeń w
    ``events_seen`` zostają (to te same id, co w ``/events``). Zebrane
    zamknięcia w starym formacie (id → gwizdek) przechodzą na klucz
    (id, gwizdek). Idempotentne.
    """
    state.pop("kickoffs", None)
    state.pop("kickoffs_seen", None)
    seen: dict[str, dict[str, str]] = state.setdefault("events_seen", {})
    for sport, bucket in seen.items():
        seen[sport] = {k: v for k, v in bucket.items() if not k.startswith(LEGACY_PREFIX)}
    for sport, bucket in state.get("closing_events", {}).items():
        state["closing_events"][sport] = {
            (k if "|" in k else f"{k}|{_utc(v).isoformat()}"): v for k, v in bucket.items()
        }
    # Stare klucze „liga|kotwica|gwizdek” w closing_missed nie są parą (id, gwizdek).
    state["closing_missed"] = [
        k for k in state.get("closing_missed", []) if k.count("|") == 1
    ]


def record_events(state: dict[str, Any], *, sport_key: str, events: list[dict[str, Any]]) -> None:
    """Terminarz z ``/events``: identyfikator → AKTUALNY gwizdek.

    Przełożenie nadpisuje gwizdek. Zdarzenie, którego lista już nie podaje,
    zostaje z ostatnim znanym gwizdkiem — chwilowo pusta odpowiedź dostawcy
    nie może wymazać terminarza tuż przed zamknięciem; mecz odwołany kończy
    się wtedy wpisem „brak rynku Pinnacle”, nie ciszą.
    """
    bucket: dict[str, str] = state.setdefault("events_seen", {}).setdefault(sport_key, {})
    for event in events:
        if event.get("id") and event.get("commence_time"):
            bucket[str(event["id"])] = _utc(event["commence_time"]).isoformat()


def prune_history(state: dict[str, Any], *, now: datetime) -> None:
    """Historia meczów, zamknięć i porażek — ``KICKOFFS_SEEN_DAYS`` dni wstecz."""
    cutoff = now - timedelta(days=KICKOFFS_SEEN_DAYS)
    for name in ("events_seen", "closing_events"):
        history: dict[str, dict[str, str]] = state.get(name, {})
        state[name] = {
            sport: {k: v for k, v in bucket.items() if _utc(v) >= cutoff}
            for sport, bucket in history.items()
        }
    for name in ("closing_failures", "closing_failure_http"):
        failures: dict[str, dict[str, Any]] = state.get(name, {})
        state[name] = {
            sport: {k: v for k, v in bucket.items() if _utc(k.rsplit("|", 1)[1]) >= cutoff}
            for sport, bucket in failures.items()
        }
    state["closing_missed"] = [
        k for k in state.get("closing_missed", []) if _utc(k.rsplit("|", 1)[1]) >= cutoff
    ]


def known_kickoffs(state: dict[str, Any]) -> dict[str, list[datetime]]:
    """Gwizdki z terminarza ``/events`` (``events_seen``) — jedyne źródło planowania."""
    return {
        sport: sorted({_utc(v) for v in bucket.values()})
        for sport, bucket in state.get("events_seen", {}).items()
    }


def closing_coverage(
    state: dict[str, Any], *, now: datetime, days: int = 7
) -> dict[str, tuple[int, int]]:
    """Pokrycie zamknięć w ostatnich ``days`` dniach: liga → (zebrane, mecze).

    Miara tygodniowa z ``ROADMAP.md`` §8; bramki G-S i G-K wymagają ≥ 95%.
    Mianownik: mecze z terminarza ``/events`` (F0d-01) z AKTUALNYM gwizdkiem.
    Zebrany: (id, ten gwizdek) w ``closing_events`` — zamknięcie z kompletem
    h2h Pinnacle dla tego terminu (F0c-04, F0d-03).
    """
    if days > KICKOFFS_SEEN_DAYS:
        raise ValueError(f"okno {days} dni dłuższe niż historia {KICKOFFS_SEEN_DAYS} dni")
    out: dict[str, tuple[int, int]] = {}
    for league in LEAGUES:
        bucket = state.get("events_seen", {}).get(league.sport_key, {})
        closed = state.get("closing_events", {}).get(league.sport_key, {})
        recent = [
            f"{k}|{_utc(v).isoformat()}"
            for k, v in bucket.items()
            if now - timedelta(days=days) <= _utc(v) <= now
        ]
        out[league.label] = (sum(1 for k in recent if k in closed), len(recent))
    return out


def schedule_empty(*, now: datetime, kickoffs: dict[str, list[datetime]]) -> list[str]:
    """Ligi bez żadnego znanego gwizdka w przyszłości — informacja w heartbeacie."""
    return [
        league.label
        for league in LEAGUES
        if not any(k > now for k in kickoffs.get(league.sport_key, []))
    ]
