"""
Test scanner — walks pytest files and checks whether drifted field names
appear in any test assertions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List


def scan_tests(directory: Path, field_names: List[str] | None = None) -> dict:
    """
    Walk pytest files under `directory`.

    If `field_names` is provided, check whether each field name appears
    in any test file (as a basic coverage heuristic).

    Returns:
        {
            "test_files": [...],
            "covered_fields": [...],
            "uncovered_fields": [...],
        }
    """
    directory = Path(directory)
    field_names = field_names or []

    test_files: List[str] = []
    all_source = ""

    for py_file in sorted(directory.rglob("test_*.py")):
        try:
            src = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        test_files.append(str(py_file.relative_to(directory)))
        all_source += src

    covered = [f for f in field_names if f in all_source]
    uncovered = [f for f in field_names if f not in all_source]

    return {
        "test_files": test_files,
        "covered_fields": covered,
        "uncovered_fields": uncovered,
    }
