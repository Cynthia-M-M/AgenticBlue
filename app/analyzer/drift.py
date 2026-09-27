"""
Drift engine — compares FrontendCall field lists against RouteContract field lists
and produces DriftReport findings.
"""
from __future__ import annotations

import re
from typing import List

from app.analyzer.contracts import DriftReport, FieldMismatch, FrontendCall, RouteContract


def _snake_to_camel(name: str) -> str:
    """Convert snake_case → camelCase.  doctor_id → doctorId"""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _camel_to_snake(name: str) -> str:
    """Convert camelCase → snake_case.  doctorId → doctor_id"""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _normalise_path(path: str) -> str:
    """Strip trailing slash and ensure leading slash."""
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def detect_drift(
    frontend_calls: List[FrontendCall],
    route_contracts: List[RouteContract],
) -> List[DriftReport]:
    """
    Match each FrontendCall to a RouteContract by (method, path) and
    compare their field sets.

    Drift types:
      FIELD_NAME_MISMATCH — frontend uses camelCase of a snake_case backend field
      MISSING_FIELD       — required backend field has no frontend equivalent at all
      EXTRA_FIELD         — frontend sends a field the backend doesn't know about
    """
    reports: List[DriftReport] = []

    # Build a lookup: (METHOD, /path) → RouteContract
    route_map = {
        (rc.method.upper(), _normalise_path(rc.path)): rc
        for rc in route_contracts
    }

    for call in frontend_calls:
        key = (call.method.upper(), _normalise_path(call.path))
        if key not in route_map:
            # No matching backend route — could be a new endpoint; skip for MVP
            continue

        rc = route_map[key]
        backend_fields = {f.name for f in rc.fields}
        frontend_fields = set(call.fields)

        mismatches: List[FieldMismatch] = []

        # Check each backend field against frontend
        for bf in sorted(backend_fields):
            if bf in frontend_fields:
                # Exact match — all good
                continue

            camel_variant = _snake_to_camel(bf)
            if camel_variant in frontend_fields:
                # Frontend is using camelCase of the snake_case backend field
                mismatches.append(
                    FieldMismatch(
                        frontend_field=camel_variant,
                        backend_field=bf,
                        drift_type="FIELD_NAME_MISMATCH",
                    )
                )
            else:
                # Backend field completely absent from frontend payload
                mismatches.append(
                    FieldMismatch(
                        frontend_field="(missing)",
                        backend_field=bf,
                        drift_type="MISSING_FIELD",
                    )
                )

        # Check for extra frontend fields (not in backend)
        backend_camel_variants = {_snake_to_camel(bf) for bf in backend_fields}
        for ff in sorted(frontend_fields):
            if ff in backend_fields:
                continue
            if ff in backend_camel_variants:
                continue  # already reported as FIELD_NAME_MISMATCH
            snake_variant = _camel_to_snake(ff)
            if snake_variant in backend_fields:
                continue  # already reported
            mismatches.append(
                FieldMismatch(
                    frontend_field=ff,
                    backend_field="(unknown)",
                    drift_type="EXTRA_FIELD",
                )
            )

        if mismatches:
            reports.append(
                DriftReport(
                    endpoint=f"{rc.method} {rc.path}",
                    frontend_file=call.file,
                    backend_file=rc.file,
                    schema_name=rc.schema_name,
                    mismatches=mismatches,
                )
            )

    return reports
