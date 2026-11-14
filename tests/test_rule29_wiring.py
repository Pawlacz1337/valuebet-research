"""Meta-test reguły 29: moduł bez wywołań poza testami to dług, nie gotowa funkcja.

Osiągalność po grafie importów od punktów wejścia — ``scripts/*.py`` i moduły
z blokiem ``if __name__ == "__main__"`` — z pominięciem testów. Moduł
nieosiągalny musi być na liście ``DORMANT`` (uśpiony) albo ``PENDING_WIRING``
(czeka na podłączenie w Filarze N), zgodnej z ``ROADMAP.md`` §2. Wpis dla
modułu osiągalnego też czerwieni test — lista ma opisywać stan, nie życzenie.

FSA #0 (2026-10-01): cały tor S i dwa moduły-sieroty (``features/base.py``,
``ingest/snapshots.py``) były niepodłączone, a nic tego nie wykrywało (F-28).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

#: Uśpione do odwołania — z uzasadnieniem w ROADMAP §2.
DORMANT: dict[str, str] = {
    "valuebet.features.base": "mechanizmy point-in-time toru M (CLAUDE.md „Mechanizmy cech”)",
}

#: Czekają na podłączenie — moduł → Filar.
PENDING_WIRING: dict[str, str] = {
    "valuebet.live.digest": "Filar 2",
}


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _modules() -> dict[str, Path]:
    return {_module_name(p): p for p in sorted((SRC / "valuebet").rglob("*.py"))}


def _imports(path: Path, package: str, known: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join([*anchor, base] if base else anchor)
            names = [base] + [f"{base}.{a.name}" for a in node.names]
        for name in names:
            parts = name.split(".")
            for i in range(len(parts), 0, -1):
                candidate = ".".join(parts[:i])
                if candidate in known:
                    found.add(candidate)
                    break
    return found


def _is_entry(path: Path) -> bool:
    return bool(re.search(r"__name__\s*==\s*[\"']__main__[\"']", path.read_text(encoding="utf-8")))


def reachable() -> set[str]:
    modules = _modules()
    known = set(modules)
    graph = {
        name: _imports(path, name if path.name == "__init__.py" else name.rsplit(".", 1)[0], known)
        for name, path in modules.items()
    }
    seen: set[str] = set()
    stack: list[str] = []
    for script in sorted((ROOT / "scripts").glob("*.py")):
        stack.extend(_imports(script, "", known))
    stack.extend(name for name, path in modules.items() if _is_entry(path))
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        # Import podmodułu wczytuje pakiety nadrzędne.
        parts = name.split(".")
        stack.extend(".".join(parts[:i]) for i in range(1, len(parts)))
        stack.extend(graph.get(name, ()))
    return seen


def _leaf_modules() -> set[str]:
    return {n for n, p in _modules().items() if p.name != "__init__.py"}


def test_every_module_is_reachable_or_listed() -> None:
    unreachable = sorted(_leaf_modules() - reachable() - set(DORMANT) - set(PENDING_WIRING))
    assert unreachable == [], (
        "moduły bez ścieżki od punktu wejścia — podłącz albo wpisz do DORMANT/"
        f"PENDING_WIRING i ROADMAP §2: {unreachable}"
    )


def test_lists_describe_reality() -> None:
    stale = sorted((set(DORMANT) | set(PENDING_WIRING)) & reachable())
    assert stale == [], f"moduły osiągalne, a nadal na liście: {stale}"
    missing = sorted((set(DORMANT) | set(PENDING_WIRING)) - _leaf_modules())
    assert missing == [], f"na liście, a nie ma takiego modułu: {missing}"


def test_lists_match_roadmap_section_two() -> None:
    text = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    start = text.index("## 2. Gdzie jesteśmy")
    section = text[start : text.index("\n## ", start + 5)]
    for name in [*DORMANT, *PENDING_WIRING]:
        short = "/".join(name.split(".")[1:]) + ".py"
        assert short in section, f"{short} nie ma wiersza w ROADMAP.md §2"
    for name, pillar in PENDING_WIRING.items():
        assert pillar.startswith("Filar "), f"{name}: brak Filaru ({pillar!r})"
