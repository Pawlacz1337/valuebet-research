"""Zapis atomowy i blokada pliku — wspólne dla stanu, manifestu i throttlingu.

Dlaczego nie ``Path.write_text``
--------------------------------
``write_text`` to truncate + zapis. Przerwany w połowie (zabity proces,
uśpienie komputera, pełny dysk) zostawia plik pusty albo ucięty — a plik
stanu kolektora niesie zbiór ``done``, którego utrata oznacza ponowne
pobranie wszystkich kotwic za kredyty (FSA #0 F-14).

Zapis idzie do pliku tymczasowego **w tym samym katalogu** (``os.replace``
jest atomowe tylko w obrębie jednego systemu plików) i dopiero potem
podmienia cel. Na Windows ``os.replace`` potrafi odbić się od
``PermissionError``, gdy antywirus albo OneDrive trzyma plik przez chwilę —
stąd kilka ponowień z krótką przerwą.

Blokada bez ``fcntl``
---------------------
``<cel>.lock`` tworzony przez ``os.open(O_CREAT | O_EXCL)`` — przenośne
między Windows i POSIX. Blokada starsza niż ``LOCK_STALE_AFTER`` jest
uznawana za porzuconą (proces zabity w trakcie) i zdejmowana. Wiek blokady
to porównanie ``time.time()`` z ``mtime`` pliku — zegar systemu plików, nie
chwila decyzji, dlatego ten moduł leży poza ``ingest/``, ``pricing/`` i
``backtest/``, gdzie zegar ścienny jest zakazany (reguła 30).
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Iterator
from pathlib import Path

__all__ = ["LOCK_STALE_AFTER_S", "LockTimeoutError", "file_lock", "write_atomic"]

#: Po tylu sekundach blokada uznawana za porzuconą.
LOCK_STALE_AFTER_S = 60.0
#: Ile czekamy na cudzą blokadę, zanim podniesiemy wyjątek.
LOCK_WAIT_S = 30.0

_REPLACE_ATTEMPTS = 5
_REPLACE_PAUSE_S = 0.2


class LockTimeoutError(RuntimeError):
    """Nie udało się wziąć blokady w ``LOCK_WAIT_S``."""


def write_atomic(path: Path, data: bytes) -> None:
    """Zapis przez plik tymczasowy w tym samym katalogu + ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(1, _REPLACE_ATTEMPTS + 1):
        try:
            tmp.replace(path)
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(_REPLACE_PAUSE_S * attempt)
        else:
            return


@contextlib.contextmanager
def file_lock(target: Path, *, wait_s: float = LOCK_WAIT_S) -> Iterator[None]:
    """Blokada ``<target>.lock`` przez ``O_CREAT | O_EXCL``, z przeterminowaniem."""
    lock = target.with_name(target.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    waited = 0.0
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue
            if age > LOCK_STALE_AFTER_S:
                lock.unlink(missing_ok=True)
                continue
            if waited >= wait_s:
                raise LockTimeoutError(f"blokada {lock} zajęta od {age:.0f} s") from None
            time.sleep(0.05)
            waited += 0.05
            continue
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        break
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)
