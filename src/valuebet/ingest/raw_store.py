"""Jedyny zapis do ``data/raw/`` i manifest sum kontrolnych (reguła 12).

Po co to istnieje
-----------------
FSA #0 F-12: reguła 12 („``data/raw/`` jest niemodyfikowalne") była
**niesprawdzalna**, bo nie było z czym porównać plików na dysku. Sumy
kontrolne da się policzyć zawsze — ale dopiero zapisane w chwili pobrania
mówią coś o przeszłości.

Dlatego każdy plik trafia do raw wyłącznie przez :meth:`RawStore.write_raw`:

1. bajty idą do pliku tymczasowego w ``data/raw/.incoming/``;
2. hash sha256 liczony z tego, co faktycznie leży na dysku;
3. przeniesienie na nazwę docelową **bez nadpisania** — istniejący plik to
   wyjątek (``os.link`` odmawia przy istniejącym celu; awaryjnie
   ``os.rename``, które na Windows też odmawia);
4. wiersz w ``data/manifest/raw_sha256.jsonl`` dopisany pod blokadą.

Nazwę generuje magazyn, nie wołający:
``<stem>.<UTC %Y%m%dT%H%M%S%fZ>.<8 znaków sha256><suffix>``. Mikrosekundy i
prefiks hasha zamykają F-17 (sześć plików z jednym stemplem); brak
dwukropków — NTFS ich nie przyjmuje.

Awaria między krokiem 3 a 4 zostawia plik bez wpisu. ``verify`` to wykrywa,
a jedyną sankcjonowaną naprawą jest ``scripts/verify_raw.py --adopt-orphan``
(wpis z ``recorded_by = "adopted-<data>"``, odnotowany w raporcie FSA).

Artefakty ignorowane przez gita, na których stoją liczby
(``reports/**/*.parquet``), mają osobny manifest tą samą funkcją hashującą.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from valuebet.fsutil import file_lock

__all__ = [
    "ARTIFACTS_MANIFEST",
    "INCOMING",
    "RAW_MANIFEST",
    "RAW_ROOT",
    "ManifestEntry",
    "RawStore",
    "manifest_anchor",
    "parquet_bytes",
    "read_manifest",
    "sha256_file",
]

log = logging.getLogger(__name__)

RAW_ROOT = Path("data/raw")
RAW_MANIFEST = Path("data/manifest/raw_sha256.jsonl")
ARTIFACTS_MANIFEST = Path("data/manifest/artifacts_sha256.jsonl")
#: Pliki w trakcie zapisu. ``verify`` je pomija.
INCOMING = ".incoming"
#: Pliki w raw, które nie są danymi (znacznik katalogu dla gita).
_IGNORED_NAMES = frozenset({".gitkeep"})
_NAME_STAMP = re.compile(r"^[.-](\d{8}T\d{6})(\d{6})?Z")


def sha256_file(path: Path) -> str:
    """sha256 pliku, strumieniowo — wspólne dla raw i artefaktów."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parquet_bytes(frame: pd.DataFrame) -> bytes:
    """Ramka jako bajty parquet — do ``write_raw``, bez zapisu na dysk."""
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    sha256: str
    bytes: int
    recorded_at: str
    recorded_by: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "path": self.path,
                "sha256": self.sha256,
                "bytes": self.bytes,
                "recorded_at": self.recorded_at,
                "recorded_by": self.recorded_by,
            },
            ensure_ascii=False,
            sort_keys=True,
        )


def read_manifest(manifest: Path) -> list[ManifestEntry]:
    if not manifest.exists():
        return []
    out: list[ManifestEntry] = []
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)
        try:
            out.append(
                ManifestEntry(
                    path=str(raw["path"]),
                    sha256=str(raw["sha256"]),
                    bytes=int(raw["bytes"]),
                    recorded_at=str(raw["recorded_at"]),
                    recorded_by=str(raw["recorded_by"]),
                )
            )
        except KeyError as exc:
            raise ValueError(f"{manifest}:{number}: brak pola {exc}") from None
    return out


def manifest_anchor(manifest: Path) -> tuple[int, str]:
    """Kotwica dla audytu: liczba wierszy i sha256 ich bajtów (prefiks).

    Następny audyt liczy hash tych samych pierwszych ``n`` wierszy — manifest
    rośnie, ale jego przeszłość nie może się zmienić.
    """
    if not manifest.exists():
        return 0, hashlib.sha256(b"").hexdigest()
    lines = [line for line in manifest.read_bytes().splitlines(keepends=True) if line.strip()]
    return len(lines), hashlib.sha256(b"".join(lines)).hexdigest()


def _stamp(*, now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("now musi być timezone-aware (reguła 2)")
    return now.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


@dataclass(frozen=True)
class RawStore:
    """Magazyn raw z manifestem. Domyślnie ``data/raw`` i ``data/manifest``."""

    root: Path = RAW_ROOT
    manifest: Path = RAW_MANIFEST
    artifacts_manifest: Path = ARTIFACTS_MANIFEST

    # -- zapis ------------------------------------------------------------

    def write_raw(
        self,
        subdir: str,
        stem: str,
        suffix: str,
        data: bytes,
        *,
        now: datetime,
        recorded_by: str = "write_raw",
    ) -> Path:
        """Zapisuje nowy plik i dopisuje go do manifestu. Nigdy nie nadpisuje."""
        if not suffix.startswith("."):
            raise ValueError(f"suffix ma zaczynać się od kropki: {suffix!r}")
        if any(sep in stem for sep in ("/", "\\", ":")) or not stem:
            raise ValueError(f"niedozwolony stem: {stem!r}")
        target_dir = self.root / subdir
        if not target_dir.resolve().is_relative_to(self.root.resolve()):
            raise ValueError(f"subdir wychodzi poza raw: {subdir!r}")
        incoming = self.root / INCOMING
        incoming.mkdir(parents=True, exist_ok=True)
        tmp = incoming / f"{uuid.uuid4().hex}.part"
        with tmp.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        digest = sha256_file(tmp)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{stem}.{_stamp(now=now)}.{digest[:8]}{suffix}"
        try:
            _move_no_overwrite(tmp, target)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        entry = ManifestEntry(
            path=target.relative_to(self.root).as_posix(),
            sha256=digest,
            bytes=len(data),
            recorded_at=now.astimezone(UTC).isoformat(),
            recorded_by=recorded_by,
        )
        self._append(self.manifest, [entry])
        log.info("raw: zapisano %s (%d B, sha256 %s…)", entry.path, entry.bytes, digest[:12])
        return target

    def record_artifacts(
        self, paths: Iterable[Path], *, now: datetime, recorded_by: str
    ) -> list[ManifestEntry]:
        """Dopisuje artefakty (ścieżki względem katalogu roboczego) do manifestu."""
        entries = [
            ManifestEntry(
                path=Path(p).as_posix(),
                sha256=sha256_file(Path(p)),
                bytes=Path(p).stat().st_size,
                recorded_at=now.astimezone(UTC).isoformat(),
                recorded_by=recorded_by,
            )
            for p in paths
        ]
        if entries:
            self._append(self.artifacts_manifest, entries)
        return entries

    def adopt(self, path: Path, *, now: datetime, recorded_by: str) -> ManifestEntry:
        """Wpis dla pliku już leżącego w raw — baseline albo sierota po awarii."""
        # Ścieżka z ``files()`` zawiera już katalog raw; z CLI — względna wobec raw.
        absolute = (
            path if path.is_absolute() or path.is_relative_to(self.root) else self.root / path
        )
        if not absolute.is_file():
            raise FileNotFoundError(absolute)
        relative = absolute.resolve().relative_to(self.root.resolve()).as_posix()
        if relative in {e.path for e in read_manifest(self.manifest)}:
            raise ValueError(f"{relative} ma już wpis w manifeście")
        entry = ManifestEntry(
            path=relative,
            sha256=sha256_file(absolute),
            bytes=absolute.stat().st_size,
            recorded_at=now.astimezone(UTC).isoformat(),
            recorded_by=recorded_by,
        )
        self._append(self.manifest, [entry])
        return entry

    def _append(self, manifest: Path, entries: list[ManifestEntry]) -> None:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(manifest), manifest.open("a", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                handle.write(entry.to_json() + "\n")

    def latest(self, subdir: str, stem: str, suffix: str) -> Path | None:
        """Najnowszy plik ``stem`` w ``subdir`` — po znaczniku czasu z nazwy.

        Rozumie nowy format (``<stem>.<UTC>Z.<hash><suffix>``) i stary
        (``<stem>-<UTC>Z<suffix>``, sprzed manifestu).
        """
        folder = self.root / subdir
        best: tuple[str, Path] | None = None
        for path in folder.glob(f"{stem}*{suffix}") if folder.exists() else ():
            rest = path.name[len(stem) :]
            if rest[:1] not in (".", "-"):
                continue
            match = _NAME_STAMP.search(rest)
            if match is None:
                continue
            key = match.group(1) + (match.group(2) or "000000")
            if best is None or key > best[0]:
                best = (key, path)
        return None if best is None else best[1]

    # -- weryfikacja ------------------------------------------------------

    def files(self) -> list[Path]:
        """Pliki danych w raw: bez ``.incoming/`` i bez ``.gitkeep``."""
        if not self.root.exists():
            return []
        return sorted(
            p
            for p in self.root.rglob("*")
            if p.is_file()
            and INCOMING not in p.relative_to(self.root).parts
            and p.name not in _IGNORED_NAMES
        )

    def verify(self) -> list[str]:
        """Lista problemów. Pusta = raw zgodne z manifestem."""
        problems: list[str] = []
        entries = read_manifest(self.manifest)
        by_path: dict[str, ManifestEntry] = {}
        for entry in entries:
            if entry.path in by_path:
                problems.append(f"{entry.path}: dwa wpisy w manifeście")
            by_path[entry.path] = entry
        on_disk = {p.relative_to(self.root).as_posix(): p for p in self.files()}
        for relative, path in sorted(on_disk.items()):
            known = by_path.get(relative)
            if known is None:
                problems.append(f"{relative}: plik bez wpisu w manifeście")
                continue
            actual = sha256_file(path)
            if actual != known.sha256:
                problems.append(
                    f"{relative}: hash niezgodny (manifest {known.sha256[:12]}…, "
                    f"dysk {actual[:12]}…)"
                )
        for relative in sorted(set(by_path) - set(on_disk)):
            problems.append(f"{relative}: wpis bez pliku")
        return problems

    def verify_artifacts(self) -> list[str]:
        """Artefakty: hash zgodny z ostatnim wpisem dla ścieżki; brak pliku = błąd."""
        problems: list[str] = []
        latest: dict[str, ManifestEntry] = {}
        for entry in read_manifest(self.artifacts_manifest):
            latest[entry.path] = entry
        for relative, entry in sorted(latest.items()):
            path = Path(relative)
            if not path.is_file():
                problems.append(f"{relative}: artefakt bez pliku")
            elif sha256_file(path) != entry.sha256:
                problems.append(f"{relative}: hash artefaktu niezgodny")
        return problems


def _move_no_overwrite(src: Path, dst: Path) -> None:
    """Przeniesienie, które odmawia przy istniejącym celu (``FileExistsError``)."""
    try:
        os.link(src, dst)
    except FileExistsError:
        raise FileExistsError(f"odmawiam nadpisania pliku w raw: {dst}") from None
    except OSError:
        # System plików bez dowiązań twardych. Windows: rename odmawia przy
        # istniejącym celu; POSIX: rename by nadpisał, więc kopia przez "xb".
        if os.name == "nt":
            try:
                src.rename(dst)
            except FileExistsError:
                raise FileExistsError(f"odmawiam nadpisania pliku w raw: {dst}") from None
            return
        with dst.open("xb") as out, src.open("rb") as inp:
            out.write(inp.read())
    src.unlink(missing_ok=True)
