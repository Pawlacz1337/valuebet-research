"""Weryfikacja ``data/raw/`` wobec manifestu sum kontrolnych (reguła 12).

Kod wyjścia 1, gdy którykolwiek plik w raw nie ma wpisu, ma hash niezgodny z
wpisem, albo wpis nie ma pliku. ``data/raw/.incoming/`` jest pomijany.
Sprawdza też artefakty z ``data/manifest/artifacts_sha256.jsonl``.

Użycie::

    uv run python scripts/verify_raw.py                      # weryfikacja
    uv run python scripts/verify_raw.py --init-baseline      # raz, 2026-10-02
    uv run python scripts/verify_raw.py --adopt-orphan <ścieżka w raw>
    uv run python scripts/verify_raw.py --record-artifacts   # reports/**/*.parquet

``--init-baseline`` wpisuje pliki istniejące przed manifestem z
``recorded_by = "baseline-<data>"``. **Integralności sprzed tej daty nie da
się udowodnić** — wpis stwierdza stan z chwili wpisania, nie z chwili
pobrania. Drugi baseline jest odrzucany.

``--adopt-orphan`` to jedyna sankcjonowana naprawa po awarii między
przeniesieniem pliku a dopisaniem manifestu (``recorded_by =
"adopted-<data>"``). Każda adopcja trafia do logu i do raportu FSA.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from valuebet.ingest.raw_store import RawStore, manifest_anchor, read_manifest

ARTIFACT_GLOB = "reports/**/*.parquet"


def main(argv: list[str] | None = None, *, store: RawStore | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weryfikacja data/raw wobec manifestu")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--init-baseline", action="store_true")
    group.add_argument("--adopt-orphan", type=Path)
    group.add_argument("--record-artifacts", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    store = store or RawStore()
    now = datetime.now(UTC)
    day = now.date().isoformat()

    if args.init_baseline:
        entries = read_manifest(store.manifest)
        if any(e.recorded_by.startswith("baseline-") for e in entries):
            print("baseline już istnieje — drugi jest odrzucany", file=sys.stderr)
            return 1
        known = {e.path for e in entries}
        added = 0
        for path in store.files():
            relative = path.relative_to(store.root).as_posix()
            if relative in known:
                continue
            entry = store.adopt(path, now=now, recorded_by=f"baseline-{day}")
            print(f"baseline: {entry.path}  {entry.sha256}")
            added += 1
        print(f"baseline: {added} plików (integralność sprzed {day} nieudowodniona)")
    elif args.adopt_orphan is not None:
        entry = store.adopt(args.adopt_orphan, now=now, recorded_by=f"adopted-{day}")
        print(f"ADOPCJA: {entry.path}  {entry.sha256}  — odnotuj w logu i w FSA")
    elif args.record_artifacts:
        recorded = {e.path: e.sha256 for e in read_manifest(store.artifacts_manifest)}
        fresh = [
            p
            for p in sorted(Path().glob(ARTIFACT_GLOB))
            if recorded.get(p.as_posix()) is None
        ]
        for entry in store.record_artifacts(fresh, now=now, recorded_by=f"artifact-{day}"):
            print(f"artefakt: {entry.path}  {entry.sha256}")

    problems = store.verify() + store.verify_artifacts()
    n_lines, digest = manifest_anchor(store.manifest)
    print(f"manifest raw: {n_lines} wierszy, sha256 wierszy {digest}")
    n_art, digest_art = manifest_anchor(store.artifacts_manifest)
    print(f"manifest artefaktów: {n_art} wierszy, sha256 wierszy {digest_art}")
    print(f"plików w raw: {len(store.files())}")
    for problem in problems:
        print(f"BŁĄD: {problem}")
    if problems:
        print(f"verify_raw: {len(problems)} problemów", file=sys.stderr)
        return 1
    print("verify_raw: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
