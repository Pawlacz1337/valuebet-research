"""FSA #0 F-23 + W.10 — werdykt walidacji instrumentu generowany z liczb.

Ścieżka niebezpieczna: ``instrument_validation.json`` mówił ``valid: true``
(kryterium bez mocy), choć CI nachylenia wykluczało 1, a stało na 6
klastrach — poniżej własnego progu wiarygodności 8.
"""

from __future__ import annotations

import importlib.util
from types import ModuleType

import pytest

from helpers import assert_from_checkout

ROOT = assert_from_checkout(__file__)


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_instrument", ROOT / "scripts" / "validate_instrument.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("ci", "clusters", "expected"),
    [
        ((0.95, 1.04), 10, "ważny"),
        ((0.81, 0.86), 10, "obciążony (skala)"),
        ((0.81, 0.86), 6, "niewiarygodny statystycznie"),
        ((0.95, 1.04), 6, "niewiarygodny statystycznie"),
        ((None, None), 3, "niewiarygodny statystycznie"),
    ],
)
def test_verdict_follows_numbers(ci: tuple[float | None, float | None], clusters: int, expected: str) -> None:
    verdict = getattr(_module(), "instrument_verdict", None)
    assert verdict is not None, "brak funkcji werdyktu — werdykt nie wynika z liczb"
    assert verdict(ci_low=ci[0], ci_high=ci[1], n_clusters=clusters) == expected


def test_old_report_has_a_note() -> None:
    assert (ROOT / "reports" / "instrument_validation.NOTE.md").is_file()
