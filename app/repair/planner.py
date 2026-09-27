"""
Repair planner — generates, applies, and verifies repairs for contract drift.
"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import List

from app.analyzer.contracts import DriftReport, RepairPlan, VerificationResult
from app.analyzer.drift import detect_drift
from app.scanner.backend import scan_backend
from app.scanner.frontend import scan_frontend

log = logging.getLogger("contractflow.repair")

# Subprocess timeout for pytest runs (seconds)
_PYTEST_TIMEOUT = 60


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------

def generate_repair_plan(
    drift_reports: List[DriftReport],
    repo_path: Path,
) -> List[RepairPlan]:
    """
    For each FIELD_NAME_MISMATCH, create a RepairPlan that renames the
    camelCase frontend field to the correct snake_case backend field.
    """
    repo_path = Path(repo_path)
    plans: List[RepairPlan] = []

    for report in drift_reports:
        for mismatch in report.mismatches:
            if mismatch.drift_type != "FIELD_NAME_MISMATCH":
                continue

            # frontend_file is relative to repo_path/frontend/
            frontend_file = repo_path / "frontend" / report.frontend_file
            regression_snippet = _build_regression_test(
                report.endpoint, mismatch.backend_field, mismatch.frontend_field
            )

            plans.append(
                RepairPlan(
                    endpoint=report.endpoint,
                    file=str(frontend_file),
                    old_text=mismatch.frontend_field,
                    new_text=mismatch.backend_field,
                    reason=(
                        f"Backend schema '{report.schema_name}' requires "
                        f"'{mismatch.backend_field}'. "
                        f"Frontend sends '{mismatch.frontend_field}' instead."
                    ),
                    risk="LOW",
                    regression_test_snippet=regression_snippet,
                )
            )

    log.info("generate_repair_plan: %d plans generated", len(plans))
    return plans


def _build_regression_test(endpoint: str, correct_field: str, wrong_field: str) -> str:
    """Generate a pytest snippet that verifies the corrected field name."""
    method, path = endpoint.split(" ", 1)
    func_name = f"test_contract_{correct_field}_field_name"
    return textwrap.dedent(f"""

        @pytest.mark.anyio
        async def {func_name}():
            \"\"\"Regression: verify frontend sends '{correct_field}', not '{wrong_field}'.\"\"\"
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.{method.lower()}(
                    "{path}",
                    json={{"patient_id": 99, "{correct_field}": 1}},
                )
            assert response.status_code == 200, (
                f"Contract regression: {{response.status_code}} — "
                f"ensure frontend sends '{correct_field}' not '{wrong_field}'"
            )
    """)


# ---------------------------------------------------------------------------
# Apply repair
# ---------------------------------------------------------------------------

def apply_repair(plan: RepairPlan) -> bool:
    """
    Apply a single RepairPlan by replacing old_text with new_text in the
    target file.  Returns True if the replacement was made, False otherwise.
    """
    target = Path(plan.file)
    if not target.exists():
        log.error("apply_repair: file not found: %s", plan.file)
        print(f"  [FAIL] File not found: {plan.file}")
        return False

    source = target.read_text(encoding="utf-8")
    if plan.old_text not in source:
        log.warning(
            "apply_repair: text '%s' not found in %s — already repaired?",
            plan.old_text, plan.file,
        )
        print(f"  [FAIL] Text '{plan.old_text}' not found in {plan.file} — already repaired?")
        return False

    patched = source.replace(plan.old_text, plan.new_text)
    target.write_text(patched, encoding="utf-8")
    log.info("apply_repair: patched %s (%s → %s)", plan.file, plan.old_text, plan.new_text)
    return True


# ---------------------------------------------------------------------------
# Add regression test
# ---------------------------------------------------------------------------

def add_regression_test(plan: RepairPlan, test_dir: Path) -> bool:
    """
    Append a regression test function to the first test_*.py file found
    under `test_dir`.  Returns True if appended, False otherwise.
    """
    test_dir = Path(test_dir)
    test_files = sorted(test_dir.rglob("test_*.py"))
    if not test_files:
        log.warning("add_regression_test: no test files found under %s", test_dir)
        print(f"  [FAIL] No test files found under {test_dir}")
        return False

    target = test_files[0]
    existing = target.read_text(encoding="utf-8")

    # Avoid duplicating the regression test
    func_sig = f"async def test_contract_{plan.new_text}_field_name"
    if func_sig in existing:
        log.info("add_regression_test: already present in %s", target.name)
        print(f"  [SKIP]  Regression test already present in {target.name}")
        return True

    # Ensure imports are present
    needs_imports = "from httpx import AsyncClient" not in existing
    import_block = ""
    if needs_imports:
        import_block = (
            "import pytest\n"
            "from httpx import AsyncClient, ASGITransport\n"
            "from demo_project.backend.main import app\n\n"
        )

    appended = existing.rstrip("\n") + "\n" + import_block + plan.regression_test_snippet
    target.write_text(appended, encoding="utf-8")
    log.info("add_regression_test: appended to %s", target.name)
    return True


# ---------------------------------------------------------------------------
# Reset demo
# ---------------------------------------------------------------------------

def reset_demo(repo_path: Path) -> None:
    """
    Reverse all applied repairs: restore camelCase field names in frontend files
    and remove appended regression tests from test files.

    This is a targeted reset for the demo scenario only.
    """
    repo_path = Path(repo_path)

    # Reset api.js: doctor_id -> doctorId
    api_js = repo_path / "frontend" / "api.js"
    if api_js.exists():
        src = api_js.read_text(encoding="utf-8")
        # Replace snake_case key back to camelCase (only the key, not the value)
        patched = re.sub(r"\bdoctor_id\b(?=\s*:)", "doctorId", src)
        if patched != src:
            api_js.write_text(patched, encoding="utf-8")
            log.info("reset_demo: reset api.js doctor_id → doctorId")
            print("  [OK] Reset api.js: doctor_id -> doctorId")
        else:
            log.info("reset_demo: api.js already in broken state")
            print("  [SKIP]  api.js already in broken state")

    # Remove regression test blocks (lines starting with the func signature)
    test_dir = repo_path / "tests"
    for tf in sorted(test_dir.rglob("test_*.py")):
        src = tf.read_text(encoding="utf-8")
        marker = "\n\n@pytest.mark.anyio\nasync def test_contract_doctor_id_field_name"
        if marker in src:
            idx = src.index(marker)
            tf.write_text(src[:idx] + "\n", encoding="utf-8")
            log.info("reset_demo: removed regression test from %s", tf.name)
            print(f"  [OK] Removed regression test from {tf.name}")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(repo_path: Path) -> VerificationResult:
    """
    Re-scan for drift and run pytest.

    Returns a VerificationResult with pass/fail counts and raw pytest output.
    """
    repo_path = Path(repo_path)
    log.info("verify: scanning repo=%s", repo_path)

    # Re-scan
    backend_contracts = scan_backend(repo_path / "backend")
    frontend_calls = scan_frontend(repo_path / "frontend")
    drift_reports = detect_drift(frontend_calls, backend_contracts)
    drift_clean = not any(r.has_drift for r in drift_reports)
    log.info("verify: drift_clean=%s", drift_clean)

    # Run pytest with a timeout to avoid hanging
    test_dir = repo_path / "tests"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_dir), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=_PYTEST_TIMEOUT,
            cwd=str(repo_path.parent),  # run from project root so imports resolve
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        log.error("verify: pytest timed out after %ds", _PYTEST_TIMEOUT)
        output = f"[ERROR] pytest timed out after {_PYTEST_TIMEOUT}s"

    # Parse pass/fail counts from pytest summary line
    passed = 0
    failed = 0
    for line in output.splitlines():
        p = re.search(r"(\d+) passed", line)
        f = re.search(r"(\d+) failed", line)
        if p:
            passed = int(p.group(1))
        if f:
            failed = int(f.group(1))

    log.info("verify: passed=%d failed=%d", passed, failed)
    return VerificationResult(
        drift_clean=drift_clean,
        tests_passed=passed,
        tests_failed=failed,
        test_output=output,
    )
