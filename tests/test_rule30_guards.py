"""Meta-test reguły 30: bezpiecznik nigdy nie jest parametrem opcjonalnym.

FSA #0 (2026-10-01): F-04 (``as_of=None``), F-19 (publiczny konstruktor
``KellyPolicy``), F-20 (``kickoffs=None``) — trzy bezpieczniki opcjonalne,
każdy z zielonym testem ścieżki bezpiecznej. To ten sam wzorzec, który dał
oba błędy KRYTYCZNE z 2026-10-01.

Test 1 (AST): parametr o nazwie z ``GUARD_PARAMS`` w funkcji albo metodzie
musi być **keyword-only, bez wartości domyślnej, z adnotacją bez ``None``**.
Pole dataclassy o takiej nazwie — bez wartości domyślnej i bez ``None`` w
typie. ``mode`` liczy się tylko w ``pricing/``, ``live/``, ``backtest/``.

Test 2 (AST): w ``pricing/``, ``backtest/``, ``live/`` i w funkcjach
bibliotecznych ``ingest/`` nie ma zegara ściennego. Zegar bierze wyłącznie
punkt wejścia (``scripts/``, funkcja ``main`` albo blok ``__main__``) i
przekazuje go dalej jako ``now``.

``GUARD_PARAMS`` może tylko rosnąć (FSA sprawdza, że lista się nie
skurczyła). ``KNOWN_VIOLATIONS`` to lista przejściowa: każdy wpis wskazuje
naprawę, która go usuwa; wpis bez naruszenia też czerwieni test. Pusta lista
jest warunkiem weryfikacji całości (``docs/FSA0_NAPRAWY.md`` §4).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "valuebet"

GUARD_PARAMS: frozenset[str] = frozenset(
    {
        "as_of",
        "now",
        "decision_time",
        "kickoffs",
        "tax_factor",
        "clv_report",
        "bankroll",
        "peak_bankroll",
        "open_exposure",
        "match_exposure",
        "edge_threshold",
        "winnings_factor",
        "bets",
        "usage_guard",
        "journal_path",
        "regime_config",
    }
)
#: ``mode`` (paper/real) jest bezpiecznikiem tylko tam, gdzie decyduje o
#: pieniądzach albo o rozliczeniu.
MODE_SCOPES = ("pricing", "live", "backtest")

GUARD_DIRS = ("pricing", "backtest", "live", "ingest", "net")
CLOCK_DIRS = ("pricing", "backtest", "live", "ingest", "net")

#: Wyjątki od listy nazw — każdy z uzasadnieniem. Audytor czyta tę stałą.
EXEMPT: dict[str, str] = {}

#: Lista przejściowa: naruszenie → naprawa, która je usuwa.
KNOWN_VIOLATIONS: dict[str, str] = {
}


def _files() -> Iterator[Path]:
    for name in GUARD_DIRS:
        folder = SRC / name
        if folder.exists():
            yield from sorted(folder.rglob("*.py"))
    yield from sorted((ROOT / "scripts").glob("*.py"))


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _scope(path: Path) -> str:
    rel = path.relative_to(ROOT).parts
    return rel[2] if rel[0] == "src" else rel[0]


def _has_none(annotation: ast.expr | None) -> bool:
    if annotation is None:
        return True  # brak adnotacji = nie wiadomo, czy None dozwolone
    text = ast.unparse(annotation)
    return "None" in text or "Optional" in text


def _is_dataclass(cls: ast.ClassDef) -> bool:
    for deco in cls.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name == "dataclass":
            return True
    return False


def _guarded(name: str, scope: str) -> bool:
    return name in GUARD_PARAMS or (name == "mode" and scope in MODE_SCOPES)


def _walk_defs(
    tree: ast.AST, prefix: str = ""
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]]:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            qual = f"{prefix}{node.name}"
            yield qual, node
            yield from _walk_defs(node, qual + ".")
        elif not isinstance(node, ast.Lambda):
            yield from _walk_defs(node, prefix)


def guard_violations() -> set[str]:
    found: set[str] = set()
    for path in _files():
        scope = _scope(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for qual, node in _walk_defs(tree):
            where = f"{_rel(path)}::{qual}"
            if isinstance(node, ast.ClassDef):
                if not _is_dataclass(node):
                    continue
                for stmt in node.body:
                    if not (
                        isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
                    ):
                        continue
                    name = stmt.target.id
                    if not _guarded(name, scope):
                        continue
                    if stmt.value is not None:
                        found.add(f"{where}::{name}::pole z wartością domyślną")
                    if _has_none(stmt.annotation):
                        found.add(f"{where}::{name}::pole dopuszcza None")
                continue
            args = node.args
            positional = [*args.posonlyargs, *args.args]
            defaults = dict(
                zip(
                    [a.arg for a in positional[len(positional) - len(args.defaults) :]],
                    args.defaults,
                    strict=True,
                )
            )
            for arg in positional:
                if _guarded(arg.arg, scope):
                    found.add(f"{where}::{arg.arg}::pozycyjny")
                    if arg.arg in defaults:
                        found.add(f"{where}::{arg.arg}::wartość domyślna")
                    if _has_none(arg.annotation):
                        found.add(f"{where}::{arg.arg}::dopuszcza None")
            for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
                if not _guarded(arg.arg, scope):
                    continue
                if default is not None:
                    found.add(f"{where}::{arg.arg}::wartość domyślna")
                if _has_none(arg.annotation):
                    found.add(f"{where}::{arg.arg}::dopuszcza None")
    return {v for v in found if v.rsplit("::", 2)[0] + "::" + v.rsplit("::", 2)[1] not in EXEMPT}


CLOCK_CALLS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("date", "today"),
    ("time", "time"),
    ("Timestamp", "now"),
    ("Timestamp", "utcnow"),
    ("Timestamp", "today"),
}


def _clock_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        owner = func.value
        owner_name = owner.attr if isinstance(owner, ast.Attribute) else getattr(owner, "id", "")
        if (owner_name, func.attr) in CLOCK_CALLS:
            return f"{owner_name}.{func.attr}"
    if isinstance(func, ast.Name) and func.id == "utcnow":
        return "utcnow"
    return None


def _main_guard(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and ast.unparse(node.test).replace("'", '"') == '__name__ == "__main__"'
    )


def clock_violations() -> set[str]:
    found: set[str] = set()
    for name in CLOCK_DIRS:
        folder = SRC / name
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for qual, node in _walk_defs(tree):
                if isinstance(node, ast.ClassDef):
                    continue
                if node.name == "main":
                    continue  # punkt wejścia modułu (python -m …)
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        clock = _clock_name(sub)
                        if clock:
                            found.add(f"{_rel(path)}::{qual}::zegar {clock}")
            for stmt in tree.body:
                if _main_guard(stmt) or isinstance(
                    stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
                ):
                    continue
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call) and _clock_name(sub):
                        found.add(f"{_rel(path)}::<moduł>::zegar {_clock_name(sub)}")
    return found


def test_guard_params_are_required_keyword_only() -> None:
    violations = guard_violations()
    new = sorted(violations - set(KNOWN_VIOLATIONS))
    assert new == [], "nowe naruszenia reguły 30:\n" + "\n".join(new)


def test_clock_only_at_entry_points() -> None:
    violations = clock_violations()
    new = sorted(violations - set(KNOWN_VIOLATIONS))
    assert new == [], "zegar ścienny poza punktem wejścia:\n" + "\n".join(new)


def test_known_violations_are_not_stale() -> None:
    current = guard_violations() | clock_violations()
    stale = sorted(set(KNOWN_VIOLATIONS) - current)
    assert stale == [], (
        "wpisy KNOWN_VIOLATIONS bez naruszenia — naprawa ma usunąć swój wpis:\n"
        + "\n".join(stale)
    )


def test_guard_list_only_grows() -> None:
    """Lista z FSA0_NAPRAWY §3 etap B. Usunięcie nazwy to osłabienie reguły 30."""
    baseline = {
        "as_of", "now", "decision_time", "kickoffs", "tax_factor", "clv_report",
        "bankroll", "peak_bankroll", "open_exposure", "match_exposure",
        "edge_threshold", "winnings_factor", "bets", "usage_guard",
        "journal_path", "regime_config",
    }  # fmt: skip
    assert baseline <= GUARD_PARAMS


def test_exemptions_are_justified() -> None:
    assert all(reason.strip() for reason in EXEMPT.values())
