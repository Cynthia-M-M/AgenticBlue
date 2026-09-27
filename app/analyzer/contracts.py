"""
Contract dataclasses — the shared data model for ContractFlow.

All scanners, the drift engine, the agent layer, and the repair planner
operate on these structures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

@dataclass
class FieldDef:
    """A single field on a Pydantic model or a frontend payload."""
    name: str
    type_annotation: str = "unknown"

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "type": self.type_annotation}


# ---------------------------------------------------------------------------
# Scanner outputs
# ---------------------------------------------------------------------------

@dataclass
class RouteContract:
    """One FastAPI route and the Pydantic schema it accepts."""
    method: str          # e.g. "POST"
    path: str            # e.g. "/appointments"
    schema_name: str     # e.g. "AppointmentCreate"
    fields: List[FieldDef] = field(default_factory=list)
    file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "schema_name": self.schema_name,
            "fields": [f.to_dict() for f in self.fields],
            "file": self.file,
        }


@dataclass
class FrontendCall:
    """One fetch/axios call in a JS file."""
    method: str          # e.g. "POST"
    path: str            # e.g. "/appointments"
    file: str            # relative path
    fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "file": self.file,
            "fields": self.fields,
        }


# ---------------------------------------------------------------------------
# Drift engine outputs
# ---------------------------------------------------------------------------

@dataclass
class FieldMismatch:
    """A single field-level mismatch between frontend and backend."""
    frontend_field: str
    backend_field: str
    drift_type: str      # "FIELD_NAME_MISMATCH" | "MISSING_FIELD" | "EXTRA_FIELD"

    def to_dict(self) -> Dict[str, str]:
        return {
            "frontend_field": self.frontend_field,
            "backend_field": self.backend_field,
            "drift_type": self.drift_type,
        }


@dataclass
class DriftReport:
    """All mismatches for one endpoint."""
    endpoint: str                          # e.g. "POST /appointments"
    frontend_file: str
    backend_file: str
    schema_name: str
    mismatches: List[FieldMismatch] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return len(self.mismatches) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "frontend_file": self.frontend_file,
            "backend_file": self.backend_file,
            "schema_name": self.schema_name,
            "mismatches": [m.to_dict() for m in self.mismatches],
        }


# ---------------------------------------------------------------------------
# Agent investigation outputs
# ---------------------------------------------------------------------------

@dataclass
class AgentFinding:
    """Structured output from one investigation agent."""
    agent_name: str
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"agent": self.agent_name, "findings": self.findings}


# ---------------------------------------------------------------------------
# Repair outputs
# ---------------------------------------------------------------------------

@dataclass
class RepairPlan:
    """A single file-level repair for one field mismatch."""
    endpoint: str
    file: str
    old_text: str
    new_text: str
    reason: str
    risk: str = "LOW"
    regression_test_snippet: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "endpoint": self.endpoint,
            "file": self.file,
            "old_text": self.old_text,
            "new_text": self.new_text,
            "reason": self.reason,
            "risk": self.risk,
        }


@dataclass
class VerificationResult:
    """Result of post-repair verification."""
    drift_clean: bool
    tests_passed: int
    tests_failed: int
    test_output: str

    # Maximum characters of pytest output to include in serialised responses
    _OUTPUT_LIMIT: int = field(default=4000, init=False, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_clean": self.drift_clean,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            # Truncate from the end to keep the most recent pytest output
            "test_output": self.test_output[-self._OUTPUT_LIMIT:],
        }
