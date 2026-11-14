"""Zamknięcie rynku — dwie stałe w jednym miejscu (reguła 28, FSA #0 F-13).

- ``CLOSING_TOLERANCE`` (30 min) — CLV przyjmuje migawkę zamknięcia z
  ``[KO - 30 min, KO]``; najpóźniejsza taka migawka jest zamknięciem.
- ``CLOSING_TARGET`` (7 min) — kolektor celuje migawką główną w
  ``[KO - 7 min, KO)``; zapasowa idzie w ``[KO - 30, KO - 7)``.

Dwie różne liczby, bo odpowiadają na różne pytania: tolerancja mówi, co
jeszcze jest zamknięciem; cel mówi, kiedy próbujemy je złapać. Trzymane w
jednym module, żeby kolektor i CLV nie rozjechały się po cichu.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Final

__all__ = ["CLOSING_TARGET", "CLOSING_TOLERANCE", "pick_closing"]

CLOSING_TOLERANCE: Final = timedelta(minutes=30)
CLOSING_TARGET: Final = timedelta(minutes=7)


def pick_closing[T](
    snapshots: Iterable[tuple[datetime, T]], *, kickoff: datetime
) -> tuple[datetime, T] | None:
    """Najpóźniejsza migawka z ``[KO - tolerancja, KO]``; brak → ``None`` (CLV n/d)."""
    eligible = [
        (observed, value)
        for observed, value in snapshots
        if kickoff - CLOSING_TOLERANCE <= observed <= kickoff
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda item: item[0])
