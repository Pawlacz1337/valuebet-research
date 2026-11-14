"""FSA #0 F-32 — każdy audyt ma wpis w ``CONTEXT.md`` §5 (pamięć długoterminowa).

Ścieżka niebezpieczna: wniosek z audytu (opcjonalny bezpiecznik = brak
bezpiecznika; zielony test ścieżki bezpiecznej nie jest dowodem) nie trafia
tam, gdzie się go czyta przed pisaniem kodu — i wzorzec wraca. Między
``AUDIT_REPORT_2`` a FSA #0 wrócił trzy razy (F-04, F-19, F-20).
"""

from __future__ import annotations

from helpers import assert_from_checkout

ROOT = assert_from_checkout(__file__)

#: Jawna lista audytów. Raport ostatniej rundy (FSA #0e) dopisany razem z
#: wpisem §5.38 w etapie H (bramka F0 → F1, 2026-10-07).
AUDITS_IN_CONTEXT = [
    "AUDIT_REPORT.md",
    "AUDIT_REPORT_2.md",
    "reports/audit/FSA_2026-10-01_F0.md",
    "reports/audit/FSA_2026-10-04_F0e.md",
]


def _section_five() -> str:
    text = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    start = text.index("## 5.")
    return text[start : text.index("\n## 6.", start)]


def test_audit_list_is_not_empty() -> None:
    assert AUDITS_IN_CONTEXT


def test_every_audit_is_referenced_in_section_five() -> None:
    section = _section_five()
    missing = [name for name in AUDITS_IN_CONTEXT if name not in section]
    assert missing == []


def test_every_audit_file_exists() -> None:
    assert [n for n in AUDITS_IN_CONTEXT if not (ROOT / n).is_file()] == []
