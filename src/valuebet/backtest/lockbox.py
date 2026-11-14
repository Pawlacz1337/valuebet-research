"""Podział deweloperski / lockbox (STEP4_ENSEMBLE §2).

Zakres
------
Lockbox to zbiór **toru M**: Ekstraklasa, sezony 2025/26 i 2026/27. Został
**zużyty 2026-10-01** jednym przebiegiem ``scripts/run_lockbox.py``
(``reports/lockbox_3433f2c.json``, rejestr ``reports/lockbox_views.jsonl``).
Drugiego przebiegu nie ma — ``run_lockbox.py`` odmawia startu przy
niepustym rejestrze. Filar 1 (backtest finansowy) lockboxa nie dotyczy:
nic tam nie jest strojone, więc sezon 2025/26 wchodzi normalnie i kod
Filaru 1 tej bramki nie woła (``BACKTEST_FIN_PLAN.md`` §1).

Po co to istnieje
-----------------
Zbiór OOS z kroku 3 (3319 meczów) był oglądany co najmniej trzy razy:
przy Elo, przy DC i przy mieszance. Diagnoza nadmiaru remisów też na nim
powstała. Każda decyzja podjęta po obejrzeniu wyniku zamienia zbiór
testowy po trochu w walidacyjny — nie przez przeciek w kodzie, tylko
przez przeciek przez głowę autora.

Dlatego dwa ostatnie sezony były odłożone i **oglądane dokładnie raz**, na
końcu kroku 4.

Etykiety sezonów
----------------
``parse_season`` jest **jedynym** miejscem zamiany etykiety sezonu na
postać kanoniczną ``RRRR/RR``. Pierwotny bezpiecznik porównywał literały
tekstowe, więc ``2025-26`` albo ``2025/2026`` przechodziły po cichu (FSA #0
F-01). Teraz każda etykieta jest parsowana, a nieczytelna to błąd, nie
„na pewno nie lockbox".

Uczciwe zastrzeżenie
--------------------
Lockbox zadeklarowano 2026-09-30, PO tym, jak log loss DC i Elo dla
2025/26 i 2026/27 pojawił się już w raportach walk-forward tej sesji.
Żadna decyzja projektowa nie została na nich oparta — regularyzacja DC
wynikła z analizy 2017/18, a kryterium strojenia odrzucono na podstawie
średniej po wszystkich sezonach. Mimo to lockbox nie jest dziewiczy w
sensie ścisłym i przy interpretacji końcowego wyniku trzeba o tym
pamiętać.
"""

from __future__ import annotations

import re

import pandas as pd

__all__ = [
    "DEV_SEASONS",
    "LOCKBOX_SEASONS",
    "assert_no_lockbox",
    "parse_season",
    "split_dev_lockbox",
]

#: Sezony, na których wolno podejmować decyzje, diagnozować i stroić.
DEV_SEASONS: tuple[str, ...] = (
    "2015/16",
    "2016/17",
    "2017/18",
    "2018/19",
    "2019/20",
    "2020/21",
    "2021/22",
    "2022/23",
    "2023/24",
    "2024/25",
)

#: Sezony odłożone. Jedna ewaluacja, wykonana 2026-10-01.
LOCKBOX_SEASONS: tuple[str, ...] = ("2025/26", "2026/27")

_SEASON = re.compile(r"^\s*(\d{4})\s*[/-]\s*(\d{2}|\d{4})\s*$")


def parse_season(label: object) -> str:
    """Etykieta sezonu → ``RRRR/RR``. Jedyne miejsce takiej zamiany.

    Przyjmuje ``2025/26``, ``2025-26``, ``2025/2026``, ``2025-2026``. Rok
    końcowy musi być początkowym + 1. Wszystko inne (``NaN``, ``25/26``,
    ``2025/27``, liczba) → ``ValueError``.
    """
    # NaN, None i liczby nie są etykietą — trafiają do tego samego błędu.
    match = _SEASON.match(label) if isinstance(label, str) else None
    if match is None:
        raise ValueError(f"nieczytelna etykieta sezonu: {label!r}")
    start = int(match.group(1))
    end_raw = match.group(2)
    expected = start + 1
    # Dwie cyfry porównujemy modulo 100 — 2099/00 jest poprawne.
    end_ok = int(end_raw) == (expected if len(end_raw) == 4 else expected % 100)
    if not end_ok:
        raise ValueError(f"sezon {label!r}: rok końcowy ma być początkowym + 1")
    return f"{start}/{expected % 100:02d}"


def _canonical(frame: pd.DataFrame, *, what: str) -> pd.Series:
    if "season" not in frame.columns:
        raise ValueError(f"{what}: brak kolumny 'season'")
    return frame["season"].map(parse_season)


def split_dev_lockbox(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """``(deweloperski, lockbox)`` po kolumnie ``season``, po parsowaniu.

    Sezony spoza obu list trafiają do deweloperskiego — nowy sezon w
    danych jest domyślnie materiałem roboczym, nie odłożonym.
    """
    is_lockbox = _canonical(frame, what="split_dev_lockbox").isin(LOCKBOX_SEASONS)
    return frame.loc[~is_lockbox].copy(), frame.loc[is_lockbox].copy()


def assert_no_lockbox(frame: pd.DataFrame, *, what: str) -> None:
    """Twardy bezpiecznik. Wołaj przed każdą liczbą, która wpływa na decyzję.

    Brak kolumny ``season``, ``NaN`` albo etykieta nie do sparsowania →
    ``ValueError``. Sezon lockboxa w dowolnym zapisie → ``RuntimeError``.
    """
    leaked = sorted(set(_canonical(frame, what=what)) & set(LOCKBOX_SEASONS))
    if leaked:
        raise RuntimeError(
            f"{what}: w zbiorze są sezony z lockboxa {leaked} — "
            "ta liczba nie może brać udziału w podejmowaniu decyzji"
        )
