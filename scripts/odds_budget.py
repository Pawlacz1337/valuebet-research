"""Przeliczenie budżetu kredytów The Odds API (TOR_S_PLAN §2).

Liczy, ile kredytów miesięcznie zje harmonogram, na podstawie
**prawdziwego terminarza** z ``state.json`` (``events_seen`` — od rundy 0e
wyłącznie z bezpłatnego ``/events``), a nie z szacunków na oko.

Symulacja, nie formuła (FSA #0e F0e-01, decyzja Pawła 2026-10-04)
-----------------------------------------------------------------
Kalkulator przechodzi **prawdziwym** ``due_calls`` kolektora co 5 min (krok
zadania) po terminarzu i sumuje należne płatne wywołania. Własna formuła
rozjechała się z kolektorem: liczyła migawki decyzyjne tylko w dni z
meczem, a kolektor robi je także dzień wcześniej (horyzont 48 h) — plan
zaniżony o ~31% kredytów decyzji. Druga implementacja tej samej reguły
należności to ten sam błąd co F-03 (reguła 28).

Dwa progi, nie jeden (FSA #0b F0b-08)
-------------------------------------
- **budżet** ``MONTHLY_BUDGET`` (450 z 500) — twardy sufit płatnych wywołań;
- **próg trybu oszczędnego** ``MONTHLY_BUDGET - CLOSINGS_ONLY_MARGIN`` (390) —
  powyżej niego ``UsageGuard`` przepuszcza wyłącznie zamknięcia główne.

Plan powyżej progu trybu oszczędnego „mieści się w budżecie”, ale przez
końcówkę każdego cyklu nie ma migawek decyzyjnych (cena wejścia toru S),
kotwic pobocznych ani zamknięć zapasowych. Terminarz z ``/events`` jest
bezpłatny — nie wchodzi do planu.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from valuebet.ingest.odds_api import CLOSINGS_ONLY_MARGIN, MONTHLY_BUDGET
from valuebet.ingest.odds_collector import (
    DECISION_HORIZON,
    LEAGUES,
    STATE_ROOT,
    due_calls,
    known_kickoffs,
)

STATE = STATE_ROOT / "state.json"
#: Od tego zużycia ``UsageGuard`` przepuszcza wyłącznie zamknięcia główne.
SAVING_THRESHOLD = MONTHLY_BUDGET - CLOSINGS_ONLY_MARGIN
#: Krok symulacji = krok zadania ``valuebet-odds`` (docs/task_scheduler.md).
STEP = timedelta(minutes=5)
#: Symulacja startuje tyle przed pierwszym gwizdkiem, żeby objąć migawkę
#: decyzyjną z dnia poprzedzającego (horyzont 48 h) i najdalszą kotwicę.
LEAD = DECISION_HORIZON + timedelta(days=1)

#: Meczów w kolejce = połowa liczby drużyn. Normalizacja po rozpiętości
#: okna terminarza NIE działa: Ekstraklasa zwraca jedną kolejkę rozpisaną
#: na 3 dni, co dawałoby „kolejka co 3 dni"; Premier League zwraca dwie
#: kolejki na 9 dni. Rozmiar ligi jest stały i znany, więc liczymy z niego.
MATCHES_PER_ROUND = {
    "soccer_poland_ekstraklasa": 9,   # 18 drużyn
    "soccer_epl": 10,                 # 20 drużyn
    "soccer_germany_bundesliga": 9,   # 18 drużyn
}

#: Kolejek w miesiącu. Ligi grają co tydzień, z przerwami na kadrę i
#: kolejkami w środku tygodnia — 4.3 to rozsądny środek.
ROUNDS_PER_MONTH = 4.3


@dataclass(frozen=True)
class BudgetPlan:
    anchors: float
    decision: float
    #: Kredytów na zamknięcia główne — jedyne, co idzie w trybie oszczędnym.
    main_closings: float
    #: Płatne wywołania i kredyty w oknie symulacji (bez skali miesięcznej).
    window_calls: int = 0
    window_credits: int = 0
    #: (liga, kotwica) → kredytów/mies. — raport per liga i typ kotwicy.
    by_kind: dict[tuple[str, str], float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return self.anchors + self.decision

    @property
    def fits_budget(self) -> bool:
        return self.total <= MONTHLY_BUDGET

    @property
    def below_saving_threshold(self) -> bool:
        return self.total <= SAVING_THRESHOLD

    @property
    def cycle_without_decision(self) -> float:
        """Odsetek cyklu w trybie oszczędnym przy równomiernym zużyciu (0 = wcale)."""
        if self.below_saving_threshold:
            return 0.0
        return 1.0 - SAVING_THRESHOLD / self.total

    def verdict(self) -> str:
        if not self.fits_budget:
            return f"NIE MIESCI SIE w budzecie {MONTHLY_BUDGET} (o {self.total - MONTHLY_BUDGET:.0f})"
        if not self.below_saving_threshold:
            return (
                f"W BUDZECIE, ale powyzej progu trybu oszczednego {SAVING_THRESHOLD}: "
                f"~{self.cycle_without_decision:.0%} cyklu bez migawek decyzyjnych, "
                "kotwic pobocznych i zamkniec zapasowych"
            )
        return f"MIESCI SIE ponizej progu trybu oszczednego {SAVING_THRESHOLD}"


def simulate(
    *, kickoffs: dict[str, list[datetime]], start: datetime, end: datetime
) -> dict[tuple[str, str], tuple[int, int]]:
    """Prawdziwe ``due_calls`` co ``STEP`` od ``start`` do ``end`` włącznie.

    Zwraca (liga, kotwica) → (wywołania, kredyty). Bez budżetu i bez trybu
    oszczędnego — to plan, nie przebieg z ograniczeniami.
    """
    done: set[str] = set()
    out: dict[tuple[str, str], tuple[int, int]] = defaultdict(lambda: (0, 0))
    t = start
    while t <= end:
        for call in due_calls(now=t, kickoffs=kickoffs, done=done):
            done.add(call.key)
            calls, cost = out[(call.league.label, call.anchor.name)]
            out[(call.league.label, call.anchor.name)] = (calls + 1, cost + call.credits)
        t += STEP
    return dict(out)


def _floor_to_step(t: datetime) -> datetime:
    minute = t.minute - t.minute % 5
    return t.replace(minute=minute, second=0, microsecond=0)


def plan(
    *,
    kickoffs: dict[str, list[datetime]],
    start: datetime | None = None,
    end: datetime | None = None,
) -> BudgetPlan:
    """Plan miesięczny z symulacji terminarza, znormalizowany do 4.3 kolejki na ligę.

    ``start``/``end`` domyślnie obejmują cały terminarz z zapasem ``LEAD``
    przed pierwszym gwizdkiem.
    """
    every = [k for games in kickoffs.values() for k in games]
    if not every:
        return BudgetPlan(anchors=0.0, decision=0.0, main_closings=0.0)
    start = start if start is not None else _floor_to_step(min(every) - LEAD)
    end = end if end is not None else max(every)
    counts = simulate(kickoffs=kickoffs, start=start, end=end)

    scale: dict[str, float] = {}
    for league in LEAGUES:
        matches = kickoffs.get(league.sport_key, [])
        rounds_in_window = max(len(matches) / MATCHES_PER_ROUND[league.sport_key], 1.0)
        scale[league.label] = ROUNDS_PER_MONTH / rounds_in_window

    by_kind = {
        key: cost * scale[key[0]] for key, (_calls, cost) in sorted(counts.items())
    }
    decision = sum(v for (_, anchor), v in by_kind.items() if anchor == "decision")
    anchors = sum(v for (_, anchor), v in by_kind.items() if anchor != "decision")
    main = sum(v for (_, anchor), v in by_kind.items() if anchor == "closing")
    return BudgetPlan(
        anchors=anchors,
        decision=decision,
        main_closings=main,
        window_calls=sum(c for c, _ in counts.values()),
        window_credits=sum(k for _, k in counts.values()),
        by_kind=by_kind,
    )


def main() -> int:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    # Gwizdki z krotnością meczów (known_kickoffs zwraca unikalne gwizdki).
    kickoffs = {
        sport: [datetime.fromisoformat(v) for v in bucket.values()]
        for sport, bucket in state.get("events_seen", {}).items()
    }
    if not any(kickoffs.values()):
        kickoffs = known_kickoffs(state)
    result = plan(kickoffs=kickoffs)
    print(f"budzet: {MONTHLY_BUDGET} kredytow/mies.; prog trybu oszczednego: {SAVING_THRESHOLD}")
    print("terminarz z /events (bezplatny) — poza planem; symulacja due_calls co 5 min")
    for (label, anchor), value in result.by_kind.items():
        print(f"  {label:15s} {anchor:15s} {value:7.1f} kredytow/mies.")
    print(f"kotwice meczowe:   {result.anchors:7.0f} kredytow/mies.")
    print(f"  w tym zamkniecia glowne: {result.main_closings:7.0f}")
    print(f"migawki decyzyjne: {result.decision:7.0f} kredytow/mies.")
    print(f"RAZEM:             {result.total:7.0f} kredytow/mies.")
    print(result.verdict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
