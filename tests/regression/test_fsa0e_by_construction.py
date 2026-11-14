"""FSA #0e — pozycje zamykane z konstrukcji (decyzja Pawła 2026-10-03, pkt 1).

Każdy test opisuje ścieżkę niebezpieczną z raportu audytora i jest czerwony
na kodzie sprzed rundy 0e:

- F0d-02: tryb oszczędny pomijał płatną sondę terminarza, więc liga po
  przerwie nie miała ani terminarza, ani zamknięć;
- F0d-03: mecz przełożony po zebraniu zamknięcia dziedziczył „zebrane”;
- F0d-05: bez sprawdzenia miejsca na dysku płatne wywołanie szło mimo
  pewnego błędu zapisu (kredyt przepadał);
- F0b-08: kalkulator budżetu znał tylko 450 (własny literał) i przy planie
  powyżej progu trybu oszczędnego (390) mówił „MIEŚCI SIĘ”;
- F0b-09: płatna ścieżka ``refresh_schedule`` bez testu — usunięta;
- bezpiecznik kosztu ``/events`` i osobny powód „brak rynku Pinnacle”.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx

from helpers import assert_from_checkout, build, fake_http
from helpers.collector_scene import Scene, event
from valuebet.ingest.odds_api import OddsApiClient, OddsApiSettings
from valuebet.ingest.odds_collector import OddsCollector, closing_coverage
from valuebet.ingest.raw_store import RawStore

ROOT = assert_from_checkout(__file__)

EPL = "soccer_epl"
KO = datetime(2026, 11, 28, 15, 0, tzinfo=UTC)


def _missed(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "state" / "closing_missed.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class _Saving(Scene):
    """Scena z licznikiem w trybie oszczędnym (used 400 z 450)."""

    def handler(self, request: httpx.Request) -> httpx.Response:
        response = super().handler(request)
        headers = dict(response.headers)
        headers.update({"x-requests-used": "400", "x-requests-remaining": "100"})
        return httpx.Response(response.status_code, content=response.content, headers=headers)


def test_f0d02_saving_mode_still_learns_schedule_and_collects_closing(tmp_path: Path) -> None:
    scene = _Saving(tmp_path)
    collector = scene.collector()
    # Liga po przerwie: stan zna tylko odległy mecz, następna kolejka jest już listowana.
    far = KO + timedelta(days=30)
    collector._save_state({"done": [], "kickoffs": {EPL: [far.isoformat()]}, "last_usage": None})
    scene.events[EPL] = [event("m", KO), event("far", far)]
    collector.run_once(now=KO - timedelta(hours=3))
    collector.run_once(now=KO - timedelta(minutes=5))
    cov = closing_coverage(collector._load_state(), now=KO + timedelta(hours=1))
    assert cov["premier_league"] == (1, 1), "tryb oszczędny zostawił ligę bez zamknięcia"


def test_f0d03_postponed_match_does_not_inherit_collected(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    collector = scene.collector()
    later = KO + timedelta(days=2)
    collector._save_state({"done": [], "kickoffs": {EPL: [KO.isoformat()]}, "last_usage": None})
    scene.events[EPL] = [event("m", KO)]
    collector.run_once(now=KO - timedelta(hours=2))
    collector.run_once(now=KO - timedelta(minutes=5))
    # Po zebraniu zamknięcia mecz przełożony o dwa dni; jego nowe zamknięcie przepada.
    scene.events[EPL] = [event("m", later)]
    collector.run_once(now=KO + timedelta(hours=1))
    cov = closing_coverage(collector._load_state(), now=later + timedelta(hours=3))
    assert cov["premier_league"] == (0, 1), "mecz przełożony odziedziczył „zebrane”"


def test_f0d05_low_disk_skips_paid_call_with_reason(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    client = OddsApiClient(http=fake_http(scene.handler), settings=OddsApiSettings(api_key="k" * 32))
    collector = build(
        OddsCollector,
        client=client,
        store=RawStore(root=tmp_path / "raw", manifest=tmp_path / "manifest.jsonl"),
        state_root=tmp_path / "state",
        free_bytes=lambda _path: 50 * 1024 * 1024,
    )
    collector._save_state({"done": [], "kickoffs": {EPL: [KO.isoformat()]}, "last_usage": None})
    scene.events[EPL] = [event("m", KO)]
    collector.run_once(now=KO - timedelta(hours=2))
    entry = collector.run_once(now=KO - timedelta(minutes=5))
    assert scene.paid_calls == [], "płatne wywołanie mimo braku miejsca na zapis"
    assert any("MB" in e for e in entry["errors"]), entry
    collector.run_once(now=KO + timedelta(minutes=5))
    (line,) = _missed(tmp_path)
    assert line["reason"] == "brak miejsca / błąd zapisu"


def test_no_pinnacle_is_reported_apart_from_collector_gaps(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    collector = scene.collector()
    scene.events[EPL] = [event("m", KO, pinnacle=False)]
    collector.run_once(now=KO - timedelta(hours=2))
    collector.run_once(now=KO - timedelta(minutes=5))
    collector.run_once(now=KO + timedelta(minutes=5))
    (line,) = _missed(tmp_path)
    assert line["reason"] == "brak rynku Pinnacle"
    assert line["collector_gap"] is False


def test_events_that_cost_credits_are_switched_off_loudly(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"x-requests-used": "5", "x-requests-remaining": "495", "x-requests-last": "1"}
        return httpx.Response(200, json=[], headers=headers)

    client = OddsApiClient(http=fake_http(handler), settings=OddsApiSettings(api_key="k" * 32))
    collector = OddsCollector(
        client=client,
        store=RawStore(root=tmp_path / "raw", manifest=tmp_path / "manifest.jsonl"),
        state_root=tmp_path / "state",
    )
    first = collector.run_once(now=KO)
    second = collector.run_once(now=KO + timedelta(hours=2))
    assert any("kosztowało" in e for e in first["errors"]), first
    assert any("wyłączone" in e for e in second["errors"]), second
    assert second["events_refreshed"] == []


def test_f0b09_paid_schedule_refresh_is_gone(tmp_path: Path) -> None:
    assert not hasattr(OddsCollector, "refresh_schedule"), "płatna ścieżka terminarza nadal istnieje"
    scene = Scene(tmp_path)
    scene.events[EPL] = [event("m", KO)]
    entry = scene.collector().refresh_events(now=KO - timedelta(days=1))
    assert scene.paid_calls == []
    assert "premier_league" in entry["events_refreshed"]


def _budget_module() -> ModuleType:
    path = ROOT / "scripts" / "odds_budget.py"
    spec = importlib.util.spec_from_file_location("odds_budget_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_f0b08_budget_script_has_no_own_copy_of_the_budget() -> None:
    tree = ast.parse((ROOT / "scripts" / "odds_budget.py").read_text(encoding="utf-8"))
    literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value == 450]
    assert literals == [], "kalkulator ma własny literał 450 — druga kopia MONTHLY_BUDGET"


def test_f0b08_plan_above_saving_threshold_is_not_declared_fine() -> None:
    module = _budget_module()
    plan = getattr(module, "plan", None)
    assert plan is not None, "kalkulator bez funkcji planu — nie da się sprawdzić werdyktu"
    # PL 20 slotów, Bundesliga 18, Ekstraklasa 4: ~430 kredytów/mies. — jak plan z
    # FSA #0b, między progiem trybu oszczędnego 390 a budżetem 450.
    start = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    games = [start + timedelta(hours=3 * i) for i in range(20)]
    result = plan(
        kickoffs={
            EPL: games,
            "soccer_germany_bundesliga": games[:18],
            "soccer_poland_ekstraklasa": games[:4],
        }
    )
    assert 390 < result.total <= 450, result.total
    verdict = result.verdict()
    assert not verdict.startswith("MIESCI SIE"), verdict
    assert "oszczedn" in verdict, verdict


def test_done_key_migration_does_not_swallow_next_kickoff(tmp_path: Path) -> None:
    """Znalezione testem niezmiennika (ziarno 2): migracja kluczy F-13 przy KAŻDYM przebiegu.

    Zamknięcie meczu o 17:15 oznaczało jako zrobione zamknięcie meczu o 18:00
    (ta sama „godzina slotu” od 17:15) — drugi mecz tracił zamknięcie po cichu.
    """
    first = KO.replace(hour=17, minute=15)
    second = KO.replace(hour=18, minute=0)
    scene = Scene(tmp_path)
    collector = scene.collector()
    collector._save_state(
        {"done": [], "kickoffs": {EPL: [first.isoformat(), second.isoformat()]}, "last_usage": None}
    )
    scene.events[EPL] = [event("a", first), event("b", second)]
    collector.run_once(now=first - timedelta(hours=2))
    collector.run_once(now=first - timedelta(minutes=5))
    collector.run_once(now=second - timedelta(minutes=5))
    cov = closing_coverage(collector._load_state(), now=second + timedelta(hours=1))
    assert cov["premier_league"] == (2, 2), cov
