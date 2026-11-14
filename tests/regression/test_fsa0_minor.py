"""FSA #0 — DROBNE sprawdzalne mechanicznie: F-07, F-11, F-18, F-22, F-30.

- F-07: punkt wejścia ``vb = valuebet.cli:main`` wskazywał nieistniejący moduł;
- F-11: ``structlog`` i ``pydantic-settings`` w zależnościach bez użycia;
  ``VB_TELEGRAM_*`` czytane przez ``digest.py``, nieobecne w ``.env.example``;
- F-18: porządek rynków w przeglądzie dnia nie znał ``h2h`` (sweep po KRYT 1);
- F-22: werdykt CLV („bije zamknięcie”) od 5 klastrów, bramka G-K od 8, a
  komunikat dla człowieka podawał 5;
- F-30: sekcja „Układ” w ``CLAUDE.md`` nie wymieniała połowy modułów.
"""

from __future__ import annotations

import re
import tomllib
from datetime import UTC, datetime, timedelta
from typing import Any

from helpers import assert_from_checkout, build
from valuebet.backtest import clv
from valuebet.live import digest

ROOT = assert_from_checkout(__file__)


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_f07_declared_entry_points_exist() -> None:
    scripts = _pyproject()["project"].get("scripts", {})
    for target in scripts.values():
        module = target.split(":")[0]
        path = ROOT / "src" / (module.replace(".", "/") + ".py")
        assert path.is_file(), f"punkt wejścia {target} wskazuje nieistniejący moduł"


def test_f11_no_unused_declared_dependencies() -> None:
    deps = " ".join(_pyproject()["project"]["dependencies"])
    assert "structlog" not in deps
    assert "pydantic-settings" not in deps


def test_f11_env_example_lists_every_variable_read_by_code() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    declared = set(re.findall(r"^(VB_[A-Z_]+)=", example, flags=re.MULTILINE))
    used: set[str] = set()
    for path in (ROOT / "src").rglob("*.py"):
        used |= set(re.findall(r"[\"'](VB_[A-Z_]+)[\"']", path.read_text(encoding="utf-8")))
    assert used - declared == set()


def test_f18_h2h_is_ordered_first() -> None:
    from valuebet.pricing.fair import FairPrice

    now = datetime(2026, 10, 24, 8, 0, tzinfo=UTC)
    prices = [
        FairPrice(match_id="m", market="totals", outcome="over", p=0.5, observed_at=now, line=2.5),
        FairPrice(match_id="m", market="h2h", outcome="home", p=0.5, observed_at=now),
    ]
    text = build(
        digest.build_digest,
        prices,
        kickoffs={"m": now + timedelta(hours=5)},
        labels={"m": "A - B"},
        leagues={"m": "L"},
        decision_time=now + timedelta(minutes=1),
        tax_factor=1.0,
        mode="paper",
        edge_threshold=0.02,
        winnings_factor=1.0,
    )
    assert text.index("home") < text.index("over 2.5")


def _report(n_clusters: int) -> Any:
    return build(
        clv.ClvReport,
        n_total=100,
        n_with_clv=100,
        n_missing=0,
        mean=0.02,
        ci_low=0.01,
        ci_high=0.03,
        n_clusters=n_clusters,
    )


def test_f22_verdict_needs_eight_clusters() -> None:
    report = _report(6)
    assert not report.beats_closing
    assert not report.unlocks_gk
    assert "8" in report.describe()
    assert _report(8).beats_closing


def test_f30_layout_names_every_module() -> None:
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    start = text.index("## Układ")
    layout = text[start : text.index("\n## ", start + 5)]
    missing = []
    for path in sorted((ROOT / "src" / "valuebet").rglob("*.py")):
        if path.name == "__init__.py":
            continue
        if path.stem not in layout:
            missing.append(path.relative_to(ROOT / "src" / "valuebet").as_posix())
    assert missing == []
