"""
ContractFlow — FastAPI web server.

Exposes REST API endpoints for the single-page UI:
  GET  /                    → serves ui/index.html
  GET  /health              → liveness + drift stats snapshot
  GET  /api/demo-path       → returns the default demo_project path
  GET  /api/drift-history   → last 20 analysis runs (in-memory audit log)
  POST /api/analyze         → scan + drift detection
  POST /api/investigate     → agent investigation
  POST /api/repair          → apply repair + add regression test
  POST /api/verify          → re-scan + run pytest
  POST /api/reset           → restore demo to broken state
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("contractflow.server")

# ── Paths ────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent          # AgenticBlue/
_UI_DIR = _ROOT / "ui"
_DEMO_PATH = _ROOT / "demo_project"

# ── In-memory audit log (last 50 runs) ───────────────────────────────────────
_audit_log: Deque[Dict[str, Any]] = deque(maxlen=50)

app = FastAPI(
    title="ContractFlow",
    version="1.0.0",
    description="Frontend–Backend API Contract Drift Detection & Repair",
)


# ── Request models ────────────────────────────────────────────────────────────

class RepoRequest(BaseModel):
    repo_path: str = str(_DEMO_PATH)

    @field_validator("repo_path")
    @classmethod
    def repo_path_must_exist(cls, v: str) -> str:
        p = Path(v)
        if not p.exists():
            raise ValueError(f"Repository path does not exist: {v}")
        if not p.is_dir():
            raise ValueError(f"Repository path is not a directory: {v}")
        return v


# ── Helper ────────────────────────────────────────────────────────────────────

def _resolve_repo(req: RepoRequest) -> Path:
    """Return a validated, resolved Path for the repo root."""
    return Path(req.repo_path).resolve()


# ── Health endpoint ───────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
def health() -> JSONResponse:
    """Liveness probe + summary stats from the most recent analysis run."""
    last = _audit_log[-1] if _audit_log else None
    return JSONResponse({
        "status": "ok",
        "version": "1.0.0",
        "total_runs": len(_audit_log),
        "last_run": last,
    })


# ── Demo path ─────────────────────────────────────────────────────────────────

@app.get("/api/demo-path", tags=["api"])
def api_demo_path() -> JSONResponse:
    return JSONResponse({"path": str(_DEMO_PATH)})


# ── Drift history ─────────────────────────────────────────────────────────────

@app.get("/api/drift-history", tags=["api"])
def api_drift_history() -> JSONResponse:
    """Return the last 20 analysis audit records (newest first)."""
    records = list(reversed(list(_audit_log)))[:20]
    return JSONResponse({"history": records, "total_runs": len(_audit_log)})


# ── Analyze ───────────────────────────────────────────────────────────────────

@app.post("/api/analyze", tags=["api"])
def api_analyze(req: RepoRequest) -> JSONResponse:
    from app.scanner.backend import scan_backend
    from app.scanner.frontend import scan_frontend
    from app.analyzer.drift import detect_drift

    repo = _resolve_repo(req)
    log.info("analyze: repo=%s", repo)

    try:
        backend_contracts = scan_backend(repo / "backend")
        frontend_calls = scan_frontend(repo / "frontend")
        drift_reports = detect_drift(frontend_calls, backend_contracts)
    except Exception as exc:
        log.exception("analyze failed for repo=%s", repo)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    drift_count = sum(1 for r in drift_reports if r.has_drift)
    log.info(
        "analyze complete: backend_routes=%d frontend_calls=%d drift=%d",
        len(backend_contracts), len(frontend_calls), drift_count,
    )

    # Record in audit log
    _audit_log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(repo),
        "backend_routes": len(backend_contracts),
        "frontend_calls": len(frontend_calls),
        "drift_count": drift_count,
    })

    return JSONResponse({
        "backend_contracts": [r.to_dict() for r in backend_contracts],
        "frontend_calls": [c.to_dict() for c in frontend_calls],
        "drift_reports": [r.to_dict() for r in drift_reports],
        "drift_count": drift_count,
    })


# ── Investigate ───────────────────────────────────────────────────────────────

@app.post("/api/investigate", tags=["api"])
def api_investigate(req: RepoRequest) -> JSONResponse:
    from app.scanner.backend import scan_backend
    from app.scanner.frontend import scan_frontend
    from app.analyzer.drift import detect_drift
    from app.analyzer.agents import (
        investigate_frontend, investigate_backend,
        investigate_impact, investigate_tests,
    )

    repo = _resolve_repo(req)
    log.info("investigate: repo=%s", repo)

    try:
        backend_contracts = scan_backend(repo / "backend")
        frontend_calls = scan_frontend(repo / "frontend")
        drift_reports = detect_drift(frontend_calls, backend_contracts)
        findings = [
            investigate_frontend(frontend_calls).to_dict(),
            investigate_backend(backend_contracts).to_dict(),
            investigate_impact(drift_reports).to_dict(),
            investigate_tests(repo / "tests", drift_reports).to_dict(),
        ]
    except Exception as exc:
        log.exception("investigate failed for repo=%s", repo)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    log.info("investigate complete: agents=%d", len(findings))
    return JSONResponse({"findings": findings})


# ── Repair ────────────────────────────────────────────────────────────────────

@app.post("/api/repair", tags=["api"])
def api_repair(req: RepoRequest) -> JSONResponse:
    from app.scanner.backend import scan_backend
    from app.scanner.frontend import scan_frontend
    from app.analyzer.drift import detect_drift
    from app.repair.planner import generate_repair_plan, apply_repair, add_regression_test

    repo = _resolve_repo(req)
    log.info("repair: repo=%s", repo)

    try:
        backend_contracts = scan_backend(repo / "backend")
        frontend_calls = scan_frontend(repo / "frontend")
        drift_reports = detect_drift(frontend_calls, backend_contracts)
        plans = generate_repair_plan(drift_reports, repo)

        applied: List[Dict[str, Any]] = []
        for plan in plans:
            ok = apply_repair(plan)
            if ok:
                add_regression_test(plan, repo / "tests")
                applied.append(plan.to_dict())
                log.info("repair applied: endpoint=%s file=%s", plan.endpoint, plan.file)
            else:
                log.warning("repair skipped: endpoint=%s", plan.endpoint)
    except Exception as exc:
        log.exception("repair failed for repo=%s", repo)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse({"repairs_applied": len(applied), "plans": applied})


# ── Verify ────────────────────────────────────────────────────────────────────

@app.post("/api/verify", tags=["api"])
def api_verify(req: RepoRequest) -> JSONResponse:
    from app.repair.planner import verify

    repo = _resolve_repo(req)
    log.info("verify: repo=%s", repo)

    try:
        result = verify(repo)
    except Exception as exc:
        log.exception("verify failed for repo=%s", repo)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    log.info(
        "verify complete: drift_clean=%s passed=%d failed=%d",
        result.drift_clean, result.tests_passed, result.tests_failed,
    )
    return JSONResponse(result.to_dict())


# ── Reset ─────────────────────────────────────────────────────────────────────

@app.post("/api/reset", tags=["api"])
def api_reset(req: RepoRequest) -> JSONResponse:
    from app.repair.planner import reset_demo

    repo = _resolve_repo(req)
    log.info("reset: repo=%s", repo)

    try:
        reset_demo(repo)
    except Exception as exc:
        log.exception("reset failed for repo=%s", repo)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse({"status": "reset", "message": "Demo restored to broken state"})


# ── Static files + root ───────────────────────────────────────────────────────

@app.get("/", tags=["ui"])
def root() -> FileResponse:
    return FileResponse(str(_UI_DIR / "index.html"))


# Mount static files last so API routes take precedence
if _UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_UI_DIR)), name="static")
