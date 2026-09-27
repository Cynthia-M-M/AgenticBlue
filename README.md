# ContractFlow

**Team:** AgenticBlue | **Hackathon:** IBM Bob 2.0

> Catch frontend–backend API drift before it becomes a production bug.

ContractFlow statically scans a repository, builds a cross-layer contract map (frontend → API route → Pydantic schema → tests), detects field-name drift between layers, and proposes + applies a verified repair — all from the command line or a single-page web UI.

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the demo — see the intentional bug detected
python -m app.main ./demo_project

# 4. Full pipeline (detect → investigate → repair → verify)
python -m app.main ./demo_project --full

# 5. Start the web UI
uvicorn app.server:app --reload
# Open http://localhost:8000
```

---

## Demo Project

`demo_project/` contains an intentional API contract drift:

- **Backend** (`AppointmentCreate`) expects `doctor_id`
- **Frontend** (`api.js`) sends `doctorId`

This causes a `422 Unprocessable Entity` error. ContractFlow detects it, investigates it, and repairs it.

---

## Architecture

```
ContractFlow (app/)
│
├── scanner/      — static analysis of backend, frontend, tests
├── analyzer/     — contract dataclasses, drift detection, agent investigation
└── repair/       — repair planner, patch application, verification
```

---

## IBM Bob Usage

This project was built using IBM Bob 2.0 in Agent mode with parallel subagents for:
- Repository understanding and scaffold generation
- Parallel investigation of frontend/backend/test layers
- Drift detection implementation and debugging
- Repair planner and verification pipeline

See [`ibm-bob-evidence/`](ibm-bob-evidence/) for task-session summaries and screenshots.

---

## Submission Checklist

- [ ] Public GitHub repository
- [ ] Demo URL
- [ ] 3-minute demo video
- [ ] Cover image
- [ ] Slide deck
- [ ] Written description
- [ ] IBM Bob usage statement
- [ ] Bob task-session screenshots in `ibm-bob-evidence/`
