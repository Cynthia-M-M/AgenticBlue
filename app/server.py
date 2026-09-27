"""
ContractFlow — FastAPI web server.

Exposes REST API endpoints for the single-page UI:
  GET  /                    → serves ui/index.html
  POST /api/analyze         → scan + drift detection
  POST /api/investigate     → agent investigation
  POST /api/repair          → apply repair + add regression test
  POST /api/verify          → re-scan + run pytest
  POST /api/reset           → restore demo to broken state
  GET  /api/demo-path       → returns the default demo_project path
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Paths ────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent          # AgenticBlue/
_UI_DIR = _ROOT / "ui"
_DEMO_PATH = _ROOT / "demo_project"

app = FastAPI(title="ContractFlow", version="1.0.0")


# ── Request/Response models ───────────────────────────────────────────────────

class RepoRequest(BaseModel):
    repo_path: str = str(_DEMO_PATH)


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/api/demo-path")
def api_demo_path():
    return JSONResponse({"path": str(_DEMO_PATH)})


@app.post("/api/analyze")
def api_analyze(req: RepoRequest) -> JSONResponse:
    from app.scanner.backend import scan_backend
    from app.scanner.frontend import scan_frontend
    from app.analyzer.drift import detect_drift

    repo = Path(req.repo_path)
    backend_contracts = scan_backend(repo / "backend")
    frontend_calls = scan_frontend(repo / "frontend")
    drift_reports = detect_drift(frontend_calls, backend_contracts)

    return JSONResponse({
        "backend_contracts": [r.to_dict() for r in backend_contracts],
        "frontend_calls": [c.to_dict() for c in frontend_calls],
        "drift_reports": [r.to_dict() for r in drift_reports],
        "drift_count": sum(1 for r in drift_reports if r.has_drift),
    })


@app.post("/api/investigate")
def api_investigate(req: RepoRequest) -> JSONResponse:
    from app.scanner.backend import scan_backend
    from app.scanner.frontend import scan_frontend
    from app.analyzer.drift import detect_drift
    from app.analyzer.agents import (
        investigate_frontend, investigate_backend,
        investigate_impact, investigate_tests,
    )

    repo = Path(req.repo_path)
    backend_contracts = scan_backend(repo / "backend")
    frontend_calls = scan_frontend(repo / "frontend")
    drift_reports = detect_drift(frontend_calls, backend_contracts)

    findings = [
        investigate_frontend(frontend_calls).to_dict(),
        investigate_backend(backend_contracts).to_dict(),
        investigate_impact(drift_reports).to_dict(),
        investigate_tests(repo / "tests", drift_reports).to_dict(),
    ]
    return JSONResponse({"findings": findings})


@app.post("/api/repair")
def api_repair(req: RepoRequest) -> JSONResponse:
    from app.scanner.backend import scan_backend
    from app.scanner.frontend import scan_frontend
    from app.analyzer.drift import detect_drift
    from app.repair.planner import generate_repair_plan, apply_repair, add_regression_test

    repo = Path(req.repo_path)
    backend_contracts = scan_backend(repo / "backend")
    frontend_calls = scan_frontend(repo / "frontend")
    drift_reports = detect_drift(frontend_calls, backend_contracts)
    plans = generate_repair_plan(drift_reports, repo)

    applied = []
    for plan in plans:
        ok = apply_repair(plan)
        if ok:
            add_regression_test(plan, repo / "tests")
            applied.append(plan.to_dict())

    return JSONResponse({"repairs_applied": len(applied), "plans": applied})


@app.post("/api/verify")
def api_verify(req: RepoRequest) -> JSONResponse:
    from app.repair.planner import verify

    result = verify(Path(req.repo_path))
    return JSONResponse(result.to_dict())


@app.post("/api/reset")
def api_reset(req: RepoRequest) -> JSONResponse:
    from app.repair.planner import reset_demo

    reset_demo(Path(req.repo_path))
    return JSONResponse({"status": "reset", "message": "Demo restored to broken state"})


# ── Static files + root ───────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(str(_UI_DIR / "index.html"))


# Mount static files last so API routes take precedence
if _UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_UI_DIR)), name="static")
