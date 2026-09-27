# ContractFlow

**Team:** AgenticBlue | **Hackathon:** IBM Bob 2.0
**Live Demo:** [contractflow-sjna.onrender.com](https://contractflow-sjna.onrender.com)

> An Autonomous Developer Workflow Engine to catch frontend–backend API drift before it becomes a production bug.

ContractFlow statically scans a repository, builds a cross-layer contract map (frontend → API route → Pydantic schema → tests), detects field-name drift between layers, and proposes + applies a verified repair — all from the command line or a single-page web UI.

---

## 🛑 The Problem: Developer Toil & Context Fragmentation
In modular architectures (like a Python/FastAPI backend connected to a frontend), an innocent change in one layer often silently breaks another. Tracing these `422 Unprocessable Entity` bugs requires massive mental context-switching, manually reading logs, and writing reactive fixes. This severely limits the scaling capability of solo developers and small teams.

## 🚀 The Solution: ContractFlow
Instead of manual tracing, ContractFlow acts as a proactive agentic system. It scans your static code repository to map dependencies and detect API drift. When a mismatch is found, it automatically traces the logic, generates the code patch, and verifies the repair.

---

## 🛠️ Quick Start (Local Development)

```bash
# 1. Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the CLI demo — see the intentional bug detected
python -m app.main ./demo_project

# 4. Run the full CLI pipeline (detect → investigate → repair → verify)
python -m app.main ./demo_project --full

# 5. Start the local Web UI
uvicorn app.server:app --reload
# Open http://localhost:10000

```

---

## 🐛 Demo Project Simulation

The `demo_project/` directory contains an intentional API contract drift:

* **Backend** (`AppointmentCreate`) expects `doctor_id`
* **Frontend** (`api.js`) sends `doctorId`

This causes a `422` error. ContractFlow detects the drift, spawns an investigation subagent, and successfully patches the mismatch.

---

## 🧠 Architecture

```text
ContractFlow (app/)
│
├── scanner/      — Static analysis of backend, frontend, and testing layers
├── analyzer/     — Contract dataclasses, drift detection, and agent investigation
└── repair/       — Repair planner, patch application, and verification workflows

```

---

## 🤖 Powered by IBM Bob 2.0

This project was built from the ground up using IBM Bob 2.0's multi-agent orchestration and full-repository context. We utilized Bob in Agent mode with parallel subagents to automate our development lifecycle:

* **Context Ingestion:** Scanned the backend/frontend layers to map dependencies and generate our base architecture.
* **Agentic Debugging:** Used parallel investigation subagents to trace logic between FastAPI routes and frontend fetch calls.
* **Workflow Automation:** Orchestrated the drift detection implementation and built the repair verification pipeline.

📁 *See the [`ibm-bob-evidence/`](https://www.google.com/search?q=ibm-bob-evidence/&utm_source=gemini) folder for our exported task-session summaries and screenshots validating our usage.*

---
