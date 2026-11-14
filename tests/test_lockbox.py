"""Lockbox toru M: parsowanie etykiet sezonu i podział dev/lockbox."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from valuebet.backtest.lockbox import (
    LOCKBOX_SEASONS,
    assert_no_lockbox,
    parse_season,
    split_dev_lockbox,
)


@pytest.mark.parametrize(
    ("label", "canonical"),
    [
        ("2025/26", "2025/26"),
        ("2025-26", "2025/26"),
        ("2025/2026", "2025/26"),
        ("2025-2026", "2025/26"),
        (" 2019 / 20 ", "2019/20"),
        ("2099/00", "2099/00"),
    ],
)
def test_parse_season_accepts_known_spellings(label: str, canonical: str) -> None:
    assert parse_season(label) == canonical


@pytest.mark.parametrize(
    "label", ["2025/27", "2025-2027", "25/26", "2025", "sezon", "", math.nan, 2025, None]
)
def test_parse_season_rejects_everything_else(label: object) -> None:
    with pytest.raises(ValueError):
        parse_season(label)


def test_split_parses_before_comparing() -> None:
    frame = pd.DataFrame({"season": ["2024/25", "2025-26", "2026/2027"], "x": [1, 2, 3]})
    dev, box = split_dev_lockbox(frame)
    assert dev["x"].tolist() == [1]
    assert box["x"].tolist() == [2, 3]
    assert_no_lockbox(dev, what="dev")


def test_split_requires_season() -> None:
    with pytest.raises(ValueError, match="season"):
        split_dev_lockbox(pd.DataFrame({"x": [1]}))


def test_clean_dev_frame_passes() -> None:
    assert_no_lockbox(pd.DataFrame({"season": ["2023/24", "2024-25"]}), what="dev")
    assert set(LOCKBOX_SEASONS) == {"2025/26", "2026/27"}
