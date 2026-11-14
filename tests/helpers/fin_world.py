"""Sztuczne światy dla testów silnika finansowego (BACKTEST_FIN_PLAN §4).

Mecz budowany wprost jako ``ReplayMatch`` + ``MatchResult``: kursy Pinnacle
odtworzone z ``p_true`` przez ``shin_forward`` (marża z ``z``), więc Shin
zwraca ``p_true`` z dokładnością solvera; kurs miękki podaje test.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from valuebet.backtest.replay import (
    CLOSING_BEFORE_KICKOFF,
    DECISION_LAG,
    SETTLE_AFTER,
    MatchResult,
    Replay,
    ReplayMatch,
)
from valuebet.pricing.fair import MarketQuote
from valuebet.pricing.shin import shin_forward

__all__ = ["T0", "WorldMatch", "build_replay", "pinnacle_odds"]

T0 = datetime(2023, 8, 11, 17, 0, tzinfo=UTC)
#: z Shina dający booksum ~1.025 na typowym 1X2 (marża ~2.5%).
Z_DEFAULT = 0.025


def pinnacle_odds(p: Sequence[float], *, z: float = Z_DEFAULT) -> tuple[float, ...]:
    return tuple(float(k) for k in shin_forward(np.asarray(p, dtype=float), z))


@dataclass(frozen=True)
class WorldMatch:
    match_id: str
    #: (p_home, p_draw, p_away) — prawda świata.
    p_1x2: tuple[float, float, float]
    #: kursy miękkiego bukmachera 1X2 (home, draw, away).
    soft_1x2: tuple[float, float, float]
    home_goals: int | None
    away_goals: int | None
    observed_at: datetime = T0
    kickoff: datetime = T0 + timedelta(hours=21)
    #: p zamknięcia; domyślnie = p_1x2.
    p_close: tuple[float, float, float] | None = None
    #: totale 2.5 — (p_over, p_under) i kursy miękkie; ``None`` = brak rynku.
    p_ou: tuple[float, float] | None = None
    soft_ou: tuple[float, float] | None = None
    soft_book: str = "bet365"


def build_replay(world: Sequence[WorldMatch]) -> Replay:
    matches: list[ReplayMatch] = []
    results: dict[str, MatchResult] = {}
    for w in world:
        closing_at = w.kickoff - CLOSING_BEFORE_KICKOFF
        decision = {
            "pinnacle": [
                MarketQuote(w.match_id, "1x2", ("home", "draw", "away"),
                            pinnacle_odds(w.p_1x2), w.observed_at),
            ],
            w.soft_book: [
                MarketQuote(w.match_id, "1x2", ("home", "draw", "away"), w.soft_1x2, w.observed_at),
            ],
        }  # fmt: skip
        closing = {
            "pinnacle": [
                MarketQuote(w.match_id, "1x2", ("home", "draw", "away"),
                            pinnacle_odds(w.p_close or w.p_1x2), closing_at),
            ],
        }  # fmt: skip
        if w.p_ou is not None and w.soft_ou is not None:
            decision["pinnacle"].append(
                MarketQuote(w.match_id, "over_under", ("over", "under"),
                            pinnacle_odds(w.p_ou), w.observed_at, line=2.5)
            )  # fmt: skip
            decision[w.soft_book].append(
                MarketQuote(w.match_id, "over_under", ("over", "under"), w.soft_ou,
                            w.observed_at, line=2.5)
            )  # fmt: skip
            closing["pinnacle"].append(
                MarketQuote(w.match_id, "over_under", ("over", "under"),
                            pinnacle_odds(w.p_ou), closing_at, line=2.5)
            )  # fmt: skip
        matches.append(
            ReplayMatch(
                match_id=w.match_id,
                league="E0",
                season="2324",
                home_team=f"{w.match_id}-h",
                away_team=f"{w.match_id}-a",
                kickoff=w.kickoff,
                observed_at=w.observed_at,
                decision_at=w.observed_at + DECISION_LAG,
                closing_at=closing_at,
                decision={b: tuple(q) for b, q in decision.items()},
                closing={b: tuple(q) for b, q in closing.items()},
            )
        )
        results[w.match_id] = MatchResult(
            w.match_id, w.home_goals, w.away_goals, w.kickoff + SETTLE_AFTER
        )
    matches.sort(key=lambda m: (m.decision_at, m.match_id))
    return Replay(matches=tuple(matches), results=results)
