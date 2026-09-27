# ContractFlow — Implementation Plan

**Team:** AgenticBlue  
**Hackathon:** IBM Bob 2.0 Hackathon  
**Product:** ContractFlow — Catch frontend–backend API drift before it becomes a production bug.

---

## Overview

ContractFlow is a developer-workflow tool that statically scans a repository, builds a cross-layer **contract map** (frontend → API → Pydantic schema → tests), detects field-name drift between layers, and proposes + applies a verified repair. The whole demo revolves around one intentional, reproducible bug: the frontend sends `doctorId` while the backend expects `doctor_id`, causing a 422 Unprocessable Entity error.

**Scope boundary:** One repository, one endpoint, one category of drift (field-name mismatch), one repair, one regression test. Nothing beyond this.

**Build order:** Broken demo → Scanner → Drift engine → Contract map → Agentic investigation → Repair → Verification → UI polish → Submission assets.

---

## Repository Layout

```
AgenticBlue/
├── app/                        # ContractFlow tool itself
│   ├── __init__.py
│   ├── main.py                 # CLI entry point
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── backend.py          # FastAPI route + Pydantic field extractor
│   │   ├── frontend.py         # JS fetch/axios field extractor
│   │   ├── database.py         # SQLModel model scanner
│   │   └── tests.py            # pytest file scanner
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── contracts.py        # Contract dataclasses + JSON serializer
│   │   └── drift.py            # Field comparison + drift classifier
│   └── repair/
│       ├── __init__.py
│       └── planner.py          # Patch generator + regression test writer
│
├── demo_project/               # The target app ContractFlow analyzes
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app with POST /appointments
│   │   └── schemas.py          # AppointmentCreate (doctor_id)
│   ├── frontend/
│   │   └── api.js              # Deliberately sends doctorId (the bug)
│   └── tests/
│       └── test_appointments.py
│
├── ui/                         # Minimal HTML/JS UI (built last)
├── ibm-bob-evidence/           # Screenshots + bob-task-summary.md
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Sub-Tasks

---

### ST-1 — Project Scaffold & Dependencies

**Status:** `[x] done`

**Intent:**  
Establish the folder structure, Python virtual environment, and initial `requirements.txt` so every subsequent sub-task has a stable foundation to build on.

**Expected Outcomes:**
- All directories and `__init__.py` stubs exist.
- `requirements.txt` lists `fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `sqlmodel`.
- `.gitignore` ignores `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.
- `README.md` contains a one-paragraph description of ContractFlow.

**Todo List:**
1. Create every directory listed in the repository layout above.
2. Create empty `__init__.py` files in `app/`, `app/scanner/`, `app/analyzer/`, `app/repair/`, `demo_project/backend/`.
3. Create stub (pass-only) Python files: `app/main.py`, `app/scanner/backend.py`, `app/scanner/frontend.py`, `app/scanner/database.py`, `app/scanner/tests.py`, `app/analyzer/contracts.py`, `app/analyzer/drift.py`, `app/repair/planner.py`.
4. Create `demo_project/frontend/api.js` and `demo_project/tests/test_appointments.py` as empty files.
5. Write `requirements.txt` with pinned packages.
6. Write `.gitignore`.
7. Write `README.md` with product name, one-sentence description, and quick-start instructions.

**Relevant Context:**
- Workspace root: `c:\IBM Hack\AgenticBlue`
- Python environment managed outside the plan (user handles `.venv` activation).
- No framework other than FastAPI + pytest needed at this stage.

---

### ST-2 — Broken Demo Application

**Status:** `[x] done`

**Intent:**  
Build the *target* application inside `demo_project/` with the intentional `doctorId` / `doctor_id` drift baked in. This establishes the "before" state that ContractFlow will later detect and fix.

**Expected Outcomes:**
- `demo_project/backend/schemas.py` defines `AppointmentCreate` with fields `patient_id: int` and `doctor_id: int`.
- `demo_project/backend/main.py` runs a FastAPI app exposing `POST /appointments` that accepts `AppointmentCreate`.
- `demo_project/frontend/api.js` sends `{ patient_id, doctorId }` — intentionally wrong.
- `demo_project/tests/test_appointments.py` contains a basic pytest test using `httpx.AsyncClient` that POSTs the correct payload and expects a 200 response (demonstrates the happy path; the frontend drift is a separate layer).
- Running the backend and sending `{ "patient_id": 1, "doctorId": 4 }` returns HTTP 422 with `doctor_id: Field required`.

**Todo List:**
1. Write `demo_project/backend/schemas.py` — `AppointmentCreate(BaseModel)` with `patient_id: int`, `doctor_id: int`.
2. Write `demo_project/backend/main.py` — FastAPI app, `POST /appointments` endpoint returning `{message, patient_id, doctor_id}`.
3. Write `demo_project/frontend/api.js` — `createAppointment` function using `fetch`, sending `{ patient_id: patientId, doctorId: doctorId }`.
4. Write `demo_project/tests/test_appointments.py` — pytest + httpx test for the correct payload (200) and one test for the broken payload (422, field error on `doctor_id`).

**Relevant Context:**
- `AppointmentCreate` must use `doctor_id` (snake_case) — the backend truth.
- `api.js` must use `doctorId` (camelCase) — the intentional lie.
- The 422 test in `test_appointments.py` is what the demo starts with as "proof of failure."

---

### ST-3 — Backend Scanner

**Status:** `[x] done`

**Intent:**  
Implement `app/scanner/backend.py` to statically parse a Python backend directory, find FastAPI route decorators, and extract the Pydantic model fields for each request body parameter.

**Expected Outcomes:**
- Given `demo_project/backend/`, the scanner returns a list of `RouteContract` objects, each containing: HTTP method, path, schema name, and list of field names with types.
- Works via Python `ast` module — no runtime import of the target project.
- Unit-testable with just the `demo_project/backend/` files.

**Todo List:**
1. Define `RouteContract` dataclass in `app/analyzer/contracts.py` (method, path, schema_name, fields: list of FieldDef).
2. Define `FieldDef` dataclass (name, type_annotation).
3. Implement `scan_backend(directory: Path) -> list[RouteContract]` in `app/scanner/backend.py`:
   - Walk `.py` files with `ast.parse`.
   - Find `@app.post`, `@app.get`, etc. decorators to extract method + path.
   - Resolve the Pydantic model name from the function signature type hint.
   - Parse the Pydantic model class to extract field names + annotations.
4. Write a quick smoke-test (can be a `__main__` block or pytest) that runs against `demo_project/backend/` and prints the found contracts.

**Relevant Context:**
- Files: `app/scanner/backend.py`, `app/analyzer/contracts.py`
- Only needs to handle the patterns used in `demo_project/backend/` — no need for generic FastAPI dependency injection resolution.
- Must NOT import or execute target code — AST only.

---

### ST-4 — Frontend Scanner

**Status:** `[x] done`

**Intent:**  
Implement `app/scanner/frontend.py` to parse JavaScript files and extract the fields being sent in `fetch`/`JSON.stringify` calls for each API endpoint.

**Expected Outcomes:**
- Given `demo_project/frontend/api.js`, the scanner returns a list of `FrontendCall` objects, each containing: HTTP method, path, and list of field names found in the request body object literal.
- Correctly extracts `doctorId` (not `doctor_id`) from the demo file.

**Todo List:**
1. Define `FrontendCall` dataclass in `app/analyzer/contracts.py` (method, path, file, fields: list of str).
2. Implement `scan_frontend(directory: Path) -> list[FrontendCall]` in `app/scanner/frontend.py`:
   - Walk `.js` files.
   - Use targeted regex to find `fetch(` calls, extract the path string and the `JSON.stringify({...})` object keys.
   - Return one `FrontendCall` per matched call site.
3. Smoke-test against `demo_project/frontend/api.js` — confirm `doctorId` appears in extracted fields.

**Relevant Context:**
- Files: `app/scanner/frontend.py`, `app/analyzer/contracts.py`
- Regex-based parsing is sufficient for the demo — no need for a full JS AST parser.
- The path in `api.js` is `"/appointments"` — the scanner should normalise it to match the backend's `/appointments`.

---

### ST-5 — Drift Engine

**Status:** `[x] done`

**Intent:**  
Implement `app/analyzer/drift.py` to compare `FrontendCall` fields against the corresponding `RouteContract` fields and produce structured `DriftReport` findings.

**Expected Outcomes:**
- `detect_drift(frontend_calls, route_contracts) -> list[DriftReport]` correctly identifies that `doctorId` (frontend) does not match `doctor_id` (backend).
- `DriftReport` contains: endpoint, frontend_file, backend_file, schema_name, mismatches list (each with frontend_field, backend_field, drift_type).
- Drift type `FIELD_NAME_MISMATCH` is emitted for `doctorId` vs `doctor_id`.
- The engine also flags `MISSING_FIELD` if a required backend field has no frontend counterpart at all.

**Todo List:**
1. Define `DriftReport` and `FieldMismatch` dataclasses in `app/analyzer/contracts.py`.
2. Implement `detect_drift` in `app/analyzer/drift.py`:
   - Match frontend calls to route contracts by path + method.
   - Compare field sets: exact matches, camelCase↔snake_case variants, missing fields.
   - Emit `FIELD_NAME_MISMATCH` when a camelCase conversion of a backend field equals the frontend field (e.g. `doctor_id` → `doctorId`).
   - Emit `MISSING_FIELD` for backend-required fields with no frontend equivalent.
3. Add `to_dict()` method on `DriftReport` for JSON output.
4. Smoke-test: run drift engine against scanner outputs from ST-3 and ST-4, confirm 1 mismatch found.

**Relevant Context:**
- Files: `app/analyzer/drift.py`, `app/analyzer/contracts.py`
- camelCase↔snake_case detection: `doctor_id` → `doctorId` is the canonical case.
- Must not produce false positives for `patient_id` (both sides match).

---

### ST-6 — CLI Entry Point

**Status:** `[x] done`

**Intent:**  
Wire all scanners and the drift engine together in `app/main.py` so the tool can be run from the command line and produces the human-readable output described in the spec.

**Expected Outcomes:**
- `python -m app.main ./demo_project` produces the exact terminal output format from the spec (ContractFlow banner, counts, drift report with file names).
- Exit code 0 when no drift found, exit code 1 when drift detected.
- JSON output available via `--json` flag (for later UI integration).

**Todo List:**
1. Implement `app/main.py` with `argparse` for `repo_path` positional arg and `--json` flag.
2. Call `scan_backend`, `scan_frontend`, `detect_drift` in sequence.
3. Print the ContractFlow banner, scan counts, and drift findings in the specified format.
4. If `--json` flag: print `json.dumps([r.to_dict() for r in reports], indent=2)`.
5. Exit with code 1 if any drift detected.
6. Run `python -m app.main ./demo_project` from `AgenticBlue/` and confirm correct output.

**Relevant Context:**
- File: `app/main.py`
- The CLI is the primary integration test — if it prints the drift for `doctorId` vs `doctor_id`, all of ST-3, ST-4, ST-5 are validated.

---

### ST-7 — Agentic Investigation Layer

**Status:** `[x] done`

**Intent:**  
Add the four-agent investigation workflow that uses IBM Bob's agentic capabilities (parallel subagents) to produce structured evidence reports for each layer: frontend contract belief, backend actual contract, impact scope, and test coverage gap.

**Expected Outcomes:**
- `app/analyzer/agents.py` contains four investigation functions: `investigate_frontend`, `investigate_backend`, `investigate_impact`, `investigate_tests`.
- Each function takes the scan outputs and returns a structured `AgentFinding` dataclass.
- `app/main.py` has an `--investigate` flag that runs all four agents and prints their findings before the drift report.
- The investigation is demonstrable in the demo video.

**Todo List:**
1. Define `AgentFinding` dataclass in `app/analyzer/contracts.py` (agent_name, findings: list[str]).
2. Implement `investigate_frontend(frontend_calls) -> AgentFinding` — summarises what the frontend believes the contract is.
3. Implement `investigate_backend(route_contracts) -> AgentFinding` — summarises what the backend actually accepts.
4. Implement `investigate_impact(drift_reports) -> AgentFinding` — lists affected features/files.
5. Implement `investigate_tests(test_dir, drift_reports) -> AgentFinding` — checks whether any test covers the drifted fields.
6. Create `app/scanner/tests.py` logic: walk pytest files, grep for field name strings, return coverage data.
7. Integrate all four into `app/main.py --investigate` output.

**Relevant Context:**
- Files: `app/analyzer/agents.py`, `app/scanner/tests.py`, `app/analyzer/contracts.py`, `app/main.py`
- These are deterministic analysis functions, not LLM calls — the "agentic" quality comes from Bob's parallel subagent workflow used *during development*, not from runtime LLM calls.
- The IBM Bob evidence screenshots in `ibm-bob-evidence/` will document the Bob-assisted parallel investigation during development.

---

### ST-8 — Repair Planner

**Status:** `[x] done`

**Intent:**  
Implement `app/repair/planner.py` to generate a repair plan, apply the file patch to fix `doctorId → doctor_id` in the frontend, and append a regression test to the test file.

**Expected Outcomes:**
- `generate_repair_plan(drift_reports, repo_path) -> list[RepairPlan]` produces a human-readable + machine-applicable plan for each mismatch.
- `apply_repair(repair_plan, repo_path)` performs the in-place string replacement in `demo_project/frontend/api.js`.
- `add_regression_test(repair_plan, test_dir)` appends a new pytest test that POSTs with the corrected field name.
- After `apply_repair`, the frontend file contains `doctor_id` instead of `doctorId`.
- `app/main.py` gains `--repair` flag that runs detect → plan → apply → add regression test.

**Todo List:**
1. Define `RepairPlan` dataclass (endpoint, file, old_text, new_text, reason, risk, regression_test_snippet).
2. Implement `generate_repair_plan` — for each `FIELD_NAME_MISMATCH`, create a `RepairPlan` targeting the frontend file.
3. Implement `apply_repair` — open the file, replace `old_text` with `new_text`, write back.
4. Implement `add_regression_test` — append a minimal pytest function that sends the corrected payload.
5. Add `--repair` flag to `app/main.py`.
6. Test: run `--repair`, confirm `api.js` now contains `doctor_id`, confirm test file has new test function.

**Relevant Context:**
- Files: `app/repair/planner.py`, `app/main.py`
- The repair must be reversible for demo resets (add `--reset` flag or document the manual reset step).
- Risk level is always `LOW` for field rename repairs in this MVP.

---

### ST-9 — Verification

**Status:** `[x] done`

**Intent:**  
After repair, re-run the scanner and drift engine to confirm zero drift, then run `pytest` on the demo project's test suite and report pass/fail counts.

**Expected Outcomes:**
- `app/main.py --verify` rescans and runs pytest.
- Terminal output shows: `CONTRACT VERIFIED ✓ — N tests passed` when drift is gone and tests pass.
- Terminal output shows `VERIFICATION FAILED` with details if any drift or test failure remains.

**Todo List:**
1. Implement `verify(repo_path) -> VerificationResult` in `app/repair/planner.py` — re-scans, re-detects drift, runs pytest via `subprocess`.
2. Define `VerificationResult` dataclass (drift_clean: bool, tests_passed: int, tests_failed: int, test_output: str).
3. Add `--verify` flag to `app/main.py` that calls `verify` and prints the summary box from the spec.
4. Add combined `--full` flag that runs: scan → investigate → repair → verify in sequence.
5. Test the full pipeline end-to-end.

**Relevant Context:**
- Files: `app/repair/planner.py`, `app/main.py`
- pytest is invoked as a subprocess: `pytest demo_project/tests/ -v`.
- The `CONTRACT VERIFIED ✓` screen is a key demo moment — the output must be visually clean.

---

### ST-10 — Minimal Web UI

**Status:** `[x] done`

**Intent:**  
Build a single-page HTML/JS UI in `ui/` that calls the ContractFlow FastAPI backend (which wraps the CLI engine) and renders the contract map, drift findings, agent investigation panels, repair action, and verification result — all for the demo video.

**Expected Outcomes:**
- `ui/index.html` with embedded CSS and vanilla JS — no build step required.
- ContractFlow FastAPI app in `app/main.py` exposes REST endpoints:
  - `POST /api/analyze` → returns JSON drift report.
  - `POST /api/investigate` → returns JSON agent findings.
  - `POST /api/repair` → applies repair, returns RepairPlan.
  - `POST /api/verify` → re-scans + runs tests, returns VerificationResult.
- UI renders five stages as described in the spec (scan, contract map, drift, investigation, verification).
- The `CONTRACT VERIFIED ✓` screen is visually clean and demo-worthy.

**Todo List:**
1. Add FastAPI REST routes to `app/main.py` (separate from the CLI path) for `/api/analyze`, `/api/investigate`, `/api/repair`, `/api/verify`.
2. Add `StaticFiles` mount for `ui/` at route `/`.
3. Write `ui/index.html` with five sections (scan → contract map → drift panel → agent panels → verification).
4. Wire each UI button to its API endpoint with `fetch`.
5. Style to a clean, dark-themed developer tool aesthetic.
6. Smoke-test the full demo flow in the browser.

**Relevant Context:**
- Files: `ui/index.html`, `app/main.py`
- Keep JavaScript in `ui/index.html` as inline `<script>` — no bundler, no framework.
- The demo path is: Analyze → (see drift) → Investigate → (see agents) → Repair → Verify → CONTRACT VERIFIED ✓.
- The UI does NOT need authentication or multi-repo support.

---

### ST-11 — IBM Bob Evidence Package

**Status:** `[x] done`

**Intent:**  
Populate `ibm-bob-evidence/` with the screenshots, task-session evidence, and written summary required by the hackathon submission. Document that IBM Bob was used in Agent mode with parallel subagents during development.

**Expected Outcomes:**
- `ibm-bob-evidence/bob-task-summary.md` describing how Bob was used for each phase.
- Placeholder filenames for screenshots (actual captures taken during development).
- README section linking to evidence.

**Todo List:**
1. Write `ibm-bob-evidence/bob-task-summary.md` — one section per phase (repository analysis, parallel investigation, drift detection, repair, tests).
2. Create placeholder `ibm-bob-evidence/README.md` listing expected screenshot filenames.
3. Update top-level `README.md` to include: product description, demo instructions, Bob usage statement, submission checklist.

**Relevant Context:**
- The hackathon requires: Bob task-session summary screenshots, evidence of Bob-assisted work, public code repository, demo URL, cover image, video, slides, written description, IBM Bob usage statement.
- Actual screenshots are captured by the developer during real Bob sessions — this sub-task only creates the written framing.

---

## Demo Reset Instructions

To reset the demo to the "broken" state after a repair has been applied:

1. Restore `demo_project/frontend/api.js` — change `doctor_id` back to `doctorId`.
2. Remove the appended regression test from `demo_project/tests/test_appointments.py`.

Or add `python -m app.main ./demo_project --reset` in ST-8 to automate this.

---

## Non-Goals (explicitly out of scope)

- Multi-repository support  
- CI/CD integration  
- GitHub/GitLab webhooks  
- LLM/GenAI runtime calls  
- Authentication  
- Multiple drift categories beyond field-name mismatch  
- Mobile or PWA  
- Kubernetes or cloud deployment  

---

## Submission Checklist

- [ ] Public GitHub repository  
- [ ] Demo URL (local `uvicorn` is acceptable; ngrok tunnel for video)  
- [ ] 3-minute demo video (0:00–0:20 failure proof, 0:20–2:35 live tool, 2:35–3:00 value summary)  
- [ ] Cover image  
- [ ] Slide deck  
- [ ] Written description  
- [ ] IBM Bob usage statement  
- [ ] Bob task-session screenshots in `ibm-bob-evidence/`  
