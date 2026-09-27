"""
Agent investigation layer — four deterministic analysis functions, one per layer.

These functions mirror the four parallel "agents" described in the ContractFlow spec:
  1. Frontend Investigator  — what does the frontend believe the contract is?
  2. Backend Investigator   — what does the backend actually accept?
  3. Impact Investigator    — what else does this mismatch affect?
  4. Test Investigator      — does the test suite catch this drift?

The "agentic" quality of this layer comes from running these investigations
in parallel during development with IBM Bob's parallel subagent workflow.
At runtime they are fast deterministic Python functions.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.analyzer.contracts import AgentFinding, DriftReport, FrontendCall, RouteContract
from app.scanner.tests import scan_tests


def investigate_frontend(frontend_calls: List[FrontendCall]) -> AgentFinding:
    """Agent 1 — summarise what the frontend believes the API contract is."""
    findings: List[str] = []
    if not frontend_calls:
        findings.append("No frontend API calls found.")
        return AgentFinding(agent_name="Frontend Investigator", findings=findings)

    for call in frontend_calls:
        findings.append(f"Endpoint: {call.method} {call.path}")
        findings.append(f"File: {call.file}")
        if call.fields:
            findings.append(f"Fields sent: {', '.join(call.fields)}")
        else:
            findings.append("Fields sent: (none detected)")
        findings.append("")

    return AgentFinding(agent_name="Frontend Investigator", findings=findings)


def investigate_backend(route_contracts: List[RouteContract]) -> AgentFinding:
    """Agent 2 — summarise what the backend actually accepts."""
    findings: List[str] = []
    if not route_contracts:
        findings.append("No backend routes found.")
        return AgentFinding(agent_name="Backend Investigator", findings=findings)

    for rc in route_contracts:
        findings.append(f"Endpoint: {rc.method} {rc.path}")
        findings.append(f"Schema: {rc.schema_name}")
        findings.append(f"File: {rc.file}")
        if rc.fields:
            field_list = ", ".join(f"{f.name}: {f.type_annotation}" for f in rc.fields)
            findings.append(f"Required fields: {field_list}")
        else:
            findings.append("Required fields: (none detected)")
        findings.append("")

    return AgentFinding(agent_name="Backend Investigator", findings=findings)


def investigate_impact(drift_reports: List[DriftReport]) -> AgentFinding:
    """Agent 3 — list affected endpoints, files, and features."""
    findings: List[str] = []
    if not drift_reports:
        findings.append("No drift detected — no impact to report.")
        return AgentFinding(agent_name="Impact Investigator", findings=findings)

    affected_files = set()
    for report in drift_reports:
        findings.append(f"Endpoint at risk: {report.endpoint}")
        affected_files.add(report.frontend_file)
        affected_files.add(report.backend_file)
        for m in report.mismatches:
            findings.append(
                f"  {m.drift_type}: frontend '{m.frontend_field}' != backend '{m.backend_field}'"
            )
        findings.append("")

    findings.append(f"Affected files ({len(affected_files)}):")
    for f in sorted(affected_files):
        findings.append(f"  {f}")

    findings.append("")
    findings.append(
        "Impact: Any request using the frontend client will fail with HTTP 422."
    )
    findings.append("Impact: Integration tests relying on the frontend client will fail.")

    return AgentFinding(agent_name="Impact Investigator", findings=findings)


def investigate_tests(
    test_dir: Path,
    drift_reports: List[DriftReport],
) -> AgentFinding:
    """Agent 4 — check whether the test suite covers the drifted fields."""
    findings: List[str] = []

    # Collect all drifted field names (both frontend and backend variants)
    drifted_fields: List[str] = []
    for report in drift_reports:
        for m in report.mismatches:
            if m.frontend_field != "(missing)":
                drifted_fields.append(m.frontend_field)
            drifted_fields.append(m.backend_field)

    if not drifted_fields:
        findings.append("No drift to check coverage for.")
        return AgentFinding(agent_name="Test Investigator", findings=findings)

    coverage = scan_tests(Path(test_dir), field_names=list(set(drifted_fields)))

    findings.append(f"Test files found: {len(coverage['test_files'])}")
    for tf in coverage["test_files"]:
        findings.append(f"  {tf}")
    findings.append("")

    if coverage["covered_fields"]:
        findings.append(f"Fields covered by tests: {', '.join(coverage['covered_fields'])}")
    if coverage["uncovered_fields"]:
        findings.append(
            f"Fields NOT covered by tests: {', '.join(coverage['uncovered_fields'])}"
        )
        findings.append("")
        findings.append(
            "[!]  No regression test verifies frontend field names against the backend contract."
        )
        findings.append("   A regression test should be added to catch future drift.")
    else:
        findings.append("[OK] All drifted fields appear in the test suite.")

    return AgentFinding(agent_name="Test Investigator", findings=findings)
