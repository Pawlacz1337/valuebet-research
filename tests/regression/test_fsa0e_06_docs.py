"""FSA #0e F0e-06 — dokumentacja kolektora i ROADMAP zgodne z kodem po rundzie 0e.

Ścieżka niebezpieczna: dokument opisuje stan sprzed F-13 / rundy 0e (krok 15
min, grupowanie po slocie godzinowym, 3 kredyty za wywołanie, brak
``/events``) — kolejna osoba czyta dokument zamiast kodu i planuje budżet
albo okna kotwic na nieaktualnych liczbach.
"""

from __future__ import annotations

from helpers import assert_from_checkout
from valuebet.ingest import odds_collector
from valuebet.ingest.odds_collector import LEAGUES, Anchor

ROOT = assert_from_checkout(__file__)


def test_sources_document_the_free_events_endpoint() -> None:
    text = (ROOT / "docs" / "sources.md").read_text(encoding="utf-8")
    section = text[text.index("## The Odds API") :]
    section = section[: section.index("\n## ", 1)]
    assert "/events" in section
    assert "3 kredyty za wywołanie" not in section


def test_collector_docstrings_match_the_code() -> None:
    module_doc = odds_collector.__doc__ or ""
    assert "slocie godzinowym" not in module_doc
    assert "3 kredyty za wywołanie" not in module_doc
    assert "15 min" not in (Anchor.__doc__ or "")
    # Każda liga ma dziś dwa rynki — docstring nie może twierdzić inaczej.
    assert {lg.credits_per_call for lg in LEAGUES} == {2}
    assert "trzema" not in module_doc


def test_roadmap_f0_row_names_the_last_round() -> None:
    text = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| **F0**"))
    assert "FSA #0e" in row
    assert "(ostatnia runda, §5)" not in row
