"""FSA #0e F0d-01 — niezmiennik kolektora na 500 scenariuszach z ziarnem.

Decyzja Pawła (2026-10-03, pkt 2): test niezmiennika zamiast testu sceny.
Trzy rundy z rzędu (F0b-01, F0c-01/02, F0d-01) naprawa zamykała ścieżkę z
reprodukcji audytora, a obok zostawała inna droga do tego samego złego
wyniku. Ten test nie opisuje żadnej ścieżki — opisuje WYNIK, który musi
zachodzić w każdym świecie:

    każdy mecz, który ``/events`` listował ≥ 60 min przed gwizdkiem, kończy
    się zamknięciem w [KO-30, KO] albo wpisem ``closing_missed`` z powodem z
    zamkniętej listy (komputer nie działał, budżet > 450, brak rynku
    Pinnacle, brak miejsca / błąd zapisu) — prawdziwym w tym świecie.

Światy (``helpers.collector_sim``): odległe mecze, dziury w terminarzu,
przełożenia, mecz wystawiony późno, zmiana godziny gwizdka, tryb oszczędny,
wyczerpany budżet, przerwy w pracy komputera, mało miejsca, błąd zapisu.
Prawdziwy ``run_once`` co 5 min fałszywego zegara, fałszywy transport.
Bez nowej zależności — generator na ``random.Random(seed)``.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest

from helpers import assert_from_checkout
from helpers.collector_sim import _judge, generate, observed, run, run_seed

assert_from_checkout(__file__)

SCENARIOS = 500
BATCHES = 10


@pytest.mark.parametrize("batch", range(BATCHES))
def test_every_listed_match_ends_closed_or_honestly_missed(batch: int) -> None:
    per = SCENARIOS // BATCHES
    seeds = range(batch * per, (batch + 1) * per)
    failures: list[str] = []
    excluded = 0
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        for _seed, violations, description, n_excluded in pool.map(run_seed, seeds):
            excluded += n_excluded
            if violations:
                failures.append(description + "\n  NARUSZENIA:\n    " + "\n    ".join(violations))
    # Decyzja Pawła 2026-10-04: test wypisuje liczbę meczów wyłączonych przez
    # zawężenie; każdy z nich ma lukę w heartbeacie (sprawdza ``run``).
    print(f"partia {batch}: wyłączonych przez zawężenie {excluded}")
    assert not failures, (
        f"{len(failures)} z {per} scenariuszy łamie niezmiennik; pierwszy kontrprzykład:\n"
        + failures[0]
    )


def test_generator_covers_every_kind_of_world() -> None:
    """Generator rzeczywiście produkuje każdy rodzaj świata z decyzji, nie tylko łatwe."""
    seen: set[str] = set()
    for seed in range(SCENARIOS):
        seen.update(generate(seed).kinds)
    required = {
        "odlegle-mecze",
        "dziura",
        "przelozony",
        "wystawiony-pozno",
        "ten-sam-gwizdek",
        "tryb-oszczedny",
        "budzet-wyczerpany",
        "przerwa-komputera",
        "malo-miejsca",
        "blad-zapisu",
        "blad-dostawcy",
        "blad-4xx",
        "limit-429",
        "blad-kontraktu",
        "sports-blad-dostawcy",
        "sports-blad-4xx",
    }
    assert required <= seen, required - seen


def test_missing_entry_still_breaks_the_invariant(tmp_path: Path) -> None:
    """Szósty powód nie osłabił niezmiennika (decyzja Pawła 2026-10-07, warunek d).

    W światach z błędami 4xx mecz bez zamknięcia i BEZ wpisu ``closing_missed``
    nadal jest naruszeniem — wyrocznia ocenia mecz z wyczyszczoną listą wpisów.
    """
    judged = 0
    for seed in range(SCENARIOS):
        world = generate(seed)
        if "blad-4xx" not in world.kinds:
            continue
        run(world, tmp_path / str(seed))
        for m in world.matches:
            if not m.covered or m.kickoff > world.end - timedelta(minutes=30):
                continue
            if not observed(world, m):
                continue
            verdict = _judge(world, m, [])
            if verdict is not None:
                assert verdict == "brak zamknięcia i brak wpisu closing_missed"
                judged += 1
        if judged >= 5:
            break
    assert judged > 0, "żaden świat 4xx nie dał meczu bez zamknięcia"
