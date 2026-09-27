"""
ContractFlow — CLI entry point.

Usage:
  python -m app.main <repo_path>                  # scan + detect drift
  python -m app.main <repo_path> --investigate    # + agent investigation
  python -m app.main <repo_path> --repair         # + apply repair + add regression test
  python -m app.main <repo_path> --verify         # + re-scan + run pytest
  python -m app.main <repo_path> --full           # all of the above
  python -m app.main <repo_path> --reset          # restore demo to broken state
  python -m app.main <repo_path> --json           # machine-readable JSON output
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

BANNER = """\
+==========================================+
|   ContractFlow  --  by AgenticBlue       |
+==========================================+"""

LINE = "-" * 42


def _hr():
    print(LINE)


def _section(title: str):
    print(f"\n{title}")
    _hr()


# ---------------------------------------------------------------------------
# Scan stage
# ---------------------------------------------------------------------------

def run_scan(repo_path: Path):
    from app.scanner.backend import scan_backend
    from app.scanner.frontend import scan_frontend
    from app.analyzer.drift import detect_drift

    backend_dir = repo_path / "backend"
    frontend_dir = repo_path / "frontend"

    backend_contracts = scan_backend(backend_dir)
    frontend_calls = scan_frontend(frontend_dir)
    drift_reports = detect_drift(frontend_calls, backend_contracts)

    return backend_contracts, frontend_calls, drift_reports


def print_scan_results(repo_path, backend_contracts, frontend_calls, drift_reports):
    print(BANNER)
    print(f"\nRepository: {repo_path}\n")
    print("Scanning...")
    print(f"  [OK] Backend routes found:       {len(backend_contracts)}")
    print(f"  [OK] Request schemas found:      {sum(1 for r in backend_contracts if r.schema_name)}")
    print(f"  [OK] Frontend API calls found:   {len(frontend_calls)}")
    print()

    drifted = [r for r in drift_reports if r.has_drift]
    if not drifted:
        print("[OK]  No contract drift detected.")
        return

    print(f"[!]   {len(drifted)} CONTRACT DRIFT DETECTED\n")
    for report in drifted:
        _hr()
        print(f"Endpoint:  {report.endpoint}")
        print(f"Schema:    {report.schema_name}")
        print()
        for m in report.mismatches:
            print(f"  [{m.drift_type}]")
            print(f"    Frontend: {m.frontend_field}")
            print(f"    Backend:  {m.backend_field}")
            print()
        print(f"  Frontend file: {report.frontend_file}")
        print(f"  Backend file:  {report.backend_file}")
        print()
        print("  Status: BROKEN")
    _hr()


# ---------------------------------------------------------------------------
# Investigate stage
# ---------------------------------------------------------------------------

def run_investigate(backend_contracts, frontend_calls, drift_reports, repo_path: Path):
    from app.analyzer.agents import (
        investigate_frontend,
        investigate_backend,
        investigate_impact,
        investigate_tests,
    )

    findings = [
        investigate_frontend(frontend_calls),
        investigate_backend(backend_contracts),
        investigate_impact(drift_reports),
        investigate_tests(repo_path / "tests", drift_reports),
    ]
    return findings


def print_investigate_results(findings):
    _section("Agent Investigation")
    for finding in findings:
        print(f"\n>> {finding.agent_name}")
        _hr()
        for line in finding.findings:
            print(f"  {line}" if line else "")
    print()


# ---------------------------------------------------------------------------
# Repair stage
# ---------------------------------------------------------------------------

def run_repair(drift_reports, repo_path: Path):
    from app.repair.planner import generate_repair_plan, apply_repair, add_regression_test

    plans = generate_repair_plan(drift_reports, repo_path)
    applied = []
    for plan in plans:
        _section(f"Repair Plan: {plan.endpoint}")
        print(f"  File:   {plan.file}")
        print(f"  Change: {plan.old_text} -> {plan.new_text}")
        print(f"  Reason: {plan.reason}")
        print(f"  Risk:   {plan.risk}")
        print()
        ok = apply_repair(plan)
        if ok:
            print(f"  [OK] Repair applied")
            reg_ok = add_regression_test(plan, repo_path / "tests")
            if reg_ok:
                print(f"  [OK] Regression test added")
            applied.append(plan)
        else:
            print(f"  [FAIL] Repair failed")
    return applied


# ---------------------------------------------------------------------------
# Verify stage
# ---------------------------------------------------------------------------

def run_verify(repo_path: Path):
    from app.repair.planner import verify

    result = verify(repo_path)
    _section("Verification")

    if result.drift_clean and result.tests_failed == 0:
        print()
        print("+-------------------------------------------+")
        print("|         CONTRACT VERIFIED  [OK]           |")
        print("|                                           |")
        print(f"|  Drift detected:    0                     |")
        print(f"|  Tests passed:      {result.tests_passed:<4}                  |")
        print(f"|  Tests failed:      {result.tests_failed:<4}                  |")
        print("|                                           |")
        print("|  API contract restored                    |")
        print("+-------------------------------------------+")
    else:
        print()
        print("+-------------------------------------------+")
        print("|         VERIFICATION FAILED  [!]          |")
        print("|                                           |")
        drift_label = "CLEAN" if result.drift_clean else "DRIFT PRESENT"
        print(f"|  Contract:          {drift_label:<22} |")
        print(f"|  Tests passed:      {result.tests_passed:<4}                  |")
        print(f"|  Tests failed:      {result.tests_failed:<4}                  |")
        print("+-------------------------------------------+")
        print()
        print("pytest output:")
        print(result.test_output[-2000:])  # last 2k chars to avoid flooding

    return result


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def run_reset(repo_path: Path):
    from app.repair.planner import reset_demo
    _section("Demo Reset")
    reset_demo(repo_path)
    print("  [OK] Demo restored to broken state")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="contractflow",
        description="ContractFlow — detect and repair frontend/backend API contract drift",
    )
    parser.add_argument("repo_path", help="Path to the repository to analyze")
    parser.add_argument("--investigate", action="store_true", help="Run agent investigation")
    parser.add_argument("--repair", action="store_true", help="Apply repair + add regression test")
    parser.add_argument("--verify", action="store_true", help="Re-scan + run pytest after repair")
    parser.add_argument("--full", action="store_true", help="Run all stages end-to-end")
    parser.add_argument("--reset", action="store_true", help="Restore demo to broken state")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable text")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        print(f"Error: path not found: {repo_path}", file=sys.stderr)
        sys.exit(2)

    # Reset mode — standalone
    if args.reset:
        run_reset(repo_path)
        sys.exit(0)

    # Scan is always run first
    backend_contracts, frontend_calls, drift_reports = run_scan(repo_path)

    if args.json:
        output = {
            "backend_contracts": [r.to_dict() for r in backend_contracts],
            "frontend_calls": [c.to_dict() for c in frontend_calls],
            "drift_reports": [r.to_dict() for r in drift_reports],
        }
        print(json.dumps(output, indent=2))
        sys.exit(1 if any(r.has_drift for r in drift_reports) else 0)

    print_scan_results(repo_path, backend_contracts, frontend_calls, drift_reports)

    do_investigate = args.investigate or args.full
    do_repair = args.repair or args.full
    do_verify = args.verify or args.full

    if do_investigate:
        findings = run_investigate(backend_contracts, frontend_calls, drift_reports, repo_path)
        print_investigate_results(findings)

    if do_repair:
        run_repair(drift_reports, repo_path)

    if do_verify:
        result = run_verify(repo_path)
        sys.exit(1 if result.tests_failed > 0 or not result.drift_clean else 0)

    # Exit 1 if drift was detected (useful for CI)
    sys.exit(1 if any(r.has_drift for r in drift_reports) else 0)


if __name__ == "__main__":
    main()
