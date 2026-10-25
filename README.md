# Dig Once — Agentic AI for Coordinated Bengaluru Roadworks

> **IBM Bobathon: Build for Bengaluru** — Hackathon Submission  
> **Status:** Working MVP · All tests passing · End-to-end demonstrable

---

## ⚠️ Important Disclaimers

- **All data is simulated demo data.** This is not an official Bengaluru government dataset.
- The Whitefield–Mahadevapura corridor is a demo scenario, not a real infrastructure record.
- Agent execution mode is **local deterministic** — no external LLM or live IBM watsonx Orchestrate connection is active in this build (see IBM Integration section below).
- This is a prototype. It does not replace official municipal planning systems.

---

## What It Does

Dig Once coordinates road excavation and utility work among road authorities, water utilities, electricity utilities, and telecom/fibre operators.

**Problem:** Independent departments dig the same road multiple times — a road is resurfaced, then a utility cuts it open weeks later.

**Solution:** A shared planning workflow where specialized agents negotiate compatible schedules, a deterministic validator checks every proposal, and a human coordinator approves the final plan.

**Core demo scenario:**
- 6 work orders across 4 departments on one corridor
- 2 deliberate conflicts seeded: WO-102 vs WO-103 (overlap) and WO-106 (post-resurfacing excavation)
- Multi-agent negotiation resolves conflicts in ≤3 rounds
- Validator accepts or rejects every proposed schedule
- Human coordinator approves/rejects with audit trail
- Emergency burst-pipe creates CRITICAL work order and triggers re-planning
- Citizen advisory in English and Kannada

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Node.js | 18+ |
| npm | 9+ |

### 1. Backend

```bash
# Install dependencies from the backend directory
cd backend
pip install -r requirements.txt

# Start the API server from the project root
cd ..
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Alternatively, start it from the backend directory
cd backend
python -m uvicorn backend.main:app --app-dir .. --host 127.0.0.1 --port 8000 --reload
```

API docs available at: http://127.0.0.1:8000/docs

### 2. Frontend

```bash
# From project root
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173

### 3. Run Tests

```bash
# From the backend directory
cd backend
python -m pytest tests/ -v

# Or from the project root
cd ..
python -m pytest backend/tests/ -v
```

---

## Project Structure

```
DigOnce/
├── backend/
│   ├── main.py                  # FastAPI app + all routes
│   ├── models.py                # Pydantic schemas
│   ├── data/
│   │   └── seed.py              # Demo seed data + reset
│   ├── services/
│   │   ├── conflict_service.py  # Conflict detection
│   │   ├── scheduler.py         # Greedy scheduling engine
│   │   ├── validator.py         # Deterministic validator
│   │   ├── orchestrator.py      # Plan generation pipeline
│   │   ├── emergency_service.py # Emergency handling
│   │   ├── advisory_service.py  # EN/KN advisory generation
│   │   └── store.py             # In-memory data store
│   ├── agents/
│   │   └── negotiation.py       # Water/Power/Fibre/Road/Mediator agents
│   ├── tests/
│   │   └── test_backend.py      # 19 tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Full dashboard (all screens)
│   │   ├── api.ts               # API client
│   │   ├── types.ts             # TypeScript types
│   │   └── index.css            # Tailwind + custom styles
│   └── vite.config.ts
└── README.md
```

---

## API Contract

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + agent mode |
| GET | `/api/work-orders` | List work orders (optional `?corridor_id=`) |
| POST | `/api/work-orders` | Create a work order |
| GET | `/api/corridors` | List corridors |
| GET | `/api/conflicts` | Detect conflicts (optional `?corridor_id=`) |
| POST | `/api/plans/generate` | Run negotiation + generate plan |
| GET | `/api/plans` | List all plans |
| GET | `/api/plans/{id}` | Get a plan |
| POST | `/api/plans/{id}/validate` | Run deterministic validation |
| POST | `/api/plans/{id}/approve` | Approve a valid plan |
| POST | `/api/plans/{id}/reject` | Reject with reason |
| POST | `/api/plans/{id}/edit` | Edit items + revalidate |
| POST | `/api/emergencies` | Report emergency |
| GET | `/api/emergencies` | List emergencies |
| GET | `/api/audit-log` | Append-only audit log |
| GET | `/api/policies` | List policies |
| POST | `/api/policies/propose` | Propose a new policy |
| POST | `/api/policies/{id}/approve` | Approve a policy |
| GET | `/api/advisories/{plan_id}` | Get EN/KN advisory for a plan |
| POST | `/api/demo/reset` | Reset all demo data |

---

## Test Results

```
19 tests, 19 passed, 0 failures

Tests cover:
1.  Conflict detection — overlap
2.  Post-resurfacing excavation detection
3.  Deadline violation detection
4.  Valid coordinated schedule
5.  Invalid schedule rejection
6.  Multi-agent negotiation (3 rounds, local deterministic mode)
7.  Plan approval flow
8.  Rejection requires reason
9.  Edit schedule + revalidation
10. Emergency creation and work order generation
11. Audit log creation
12. Advisory EN + Kannada unicode
13. Policy proposal + approval
14. Exam period policy regression
15. API 404 error handling (plan)
16. API 404 error handling (advisory)
17. Demo reset repeatability
18. Seed data has ≥2 conflicts
19. Duplicate emergency protection
```

---

## Demo Script (Live Walkthrough)

### Step 1 — Overview
Open http://localhost:5173. Show the dashboard: 6 work orders, 2 conflicts detected, 0 approvals.

### Step 2 — Corridor Planning
Click **Corridor Planning**. Show the Gantt timeline — red bars are conflicting work orders (WO-102 vs WO-103 overlapping, WO-106 cutting a freshly surfaced road). Show the conflict detail cards.

### Step 3 — Negotiation
Click **Negotiation Center** → **Run Negotiation**.
- 3 rounds of agent proposals appear
- Before/After metrics table: resurfacing conflicts drop from 1 to 0, road openings reduce
- Bar chart shows the improvement
- Coordinated Gantt shows utility work bundled before resurfacing

### Step 4 — Approval
Click **Approval Center**. The generated plan is pre-selected.
- Validation: PASSED, Score 94/100
- Click **Approve Plan** — plan status changes to `approved`, audit entry recorded.

### Step 5 — Emergency
Click **Emergency**. Fill in description and location. Click **Report Emergency**.
- New CRITICAL work order `EM-WO-*` is created
- Go back to Negotiation and run again — emergency order appears in the new plan

### Step 6 — Policy & Audit
Click **Policy & Audit**.
- Show 3 default policies (resurfacing moratorium, trench sharing, exam period demo)
- Propose a new policy with start/end dates → approve it
- Switch to Audit Log — all actions are recorded

### Step 7 — Citizen Advisory
Click **Citizen Advisory**. Select the approved plan.
- Toggle **EN / ಕನ್ನಡ** to switch language
- Click **Read Aloud** for text-to-speech (browser must support Web Speech API)

### Step 8 — Reset
Click **Reset Demo** in sidebar to restore all seed data for a clean repeat.

---

## Architecture

```
Browser (React/Vite)
       │
       │ REST / JSON
       ▼
FastAPI Backend (Python)
  ├── Conflict Detection Service
  ├── Orchestrator
  │     ├── MediatorAgent
  │     │     ├── WaterAgent  (deterministic strategy)
  │     │     ├── PowerAgent  (bundle-seeking)
  │     │     ├── FibreAgent  (most flexible)
  │     │     └── RoadAgent   (fixed anchor)
  │     ├── Greedy Scheduler
  │     └── Deterministic Validator  ← never bypassed
  ├── Emergency Service
  ├── Advisory Service (EN + KN)
  ├── Policy Registry
  └── In-Memory Store (replaceable with SQLite/Postgres)
```

---

## IBM Technology Integration

### IBM Bob (Used throughout development)
IBM Bob was used as the engineering partner for:
- Designing and scaffolding the entire project structure
- Implementing all backend services, agents, and API routes
- Writing all 19 tests
- Diagnosing and fixing TypeScript and Python errors
- Reviewing security (no secrets committed, input validation, audit log)
- Implementing the controlled policy-change workflow

### IBM watsonx Orchestrate
**Current status: local_deterministic adapter active.**

The agent orchestration layer is built behind an adapter interface (`backend/agents/negotiation.py`). The current implementation uses local deterministic Python agents — explicitly labeled in the UI as "Local Deterministic Agents" mode.

**What `local_deterministic` does:**
- Water/Power/Fibre/Road agents run strategy-based Python functions
- Mediator runs up to 3 negotiation rounds
- All outputs are structured (typed Pydantic models), not free text
- Fully testable without any external service

**To connect watsonx Orchestrate when credentials are available:**
1. Create a `WatsonxOrchestrateAdapter` class implementing the same `negotiate()` interface
2. Set `AGENT_MODE=watsonx_orchestrate` in environment
3. Provide `WATSONX_API_KEY` and `WATSONX_PROJECT_ID` environment variables
4. The deterministic validator always runs regardless of orchestration mode

The UI clearly shows the active execution mode on the Negotiation Center screen.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MODE` | `local_deterministic` | `local_deterministic` or `watsonx_orchestrate` |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | CORS origins |
| `WATSONX_API_KEY` | — | watsonx Orchestrate API key (not used in local mode) |
| `WATSONX_PROJECT_ID` | — | watsonx project ID (not used in local mode) |

**No secrets are committed to the repository.**

---

## Scheduling Algorithm

The greedy scheduler (`backend/services/scheduler.py`):

1. Sort work orders by priority → deadline → delay cost
2. For each order, find the earliest valid start date within its allowed window
3. Enforce resurfacing moratorium (hard constraint)
4. Detect bundle opportunities (utility orders within 7 days share a trench)
5. Round 3 mediator forces bundle alignment

**Scoring function** (higher = better, 0–100):
```
score = 100
      - (road_openings × 10)
      - (resurfacing_conflicts × 20)
      - (total_delay_cost / 100,000 × 1)
      - (hard_violations × 30)
```

---

## Security

- All request bodies validated with Pydantic
- No user-supplied code is executed
- Policy changes require human approval before taking effect
- Audit log is append-only in the current store
- No secrets in source code
- Environment-based configuration only
- Duplicate emergency submission protection (5-minute window)
- Server-side validation is always run before approval; client cannot bypass it

---

## Known Limitations (MVP)

- In-memory store: data resets on server restart (by design for demo)
- No authentication/authorization (documented — not implemented in MVP)
- No real-time municipal data integration
- watsonx Orchestrate integration requires credentials not yet configured
- Distance-based proximity rules (e.g. 200m from schools) use corridor-level matching, not GPS coordinates in this build

---

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| Frontend starts | ✅ `npm run dev` |
| Backend starts | ✅ `uvicorn backend.main:app` |
| Seeded scenario loads | ✅ 6 work orders, 1 corridor |
| ≥2 conflicts from seed data | ✅ 2 confirmed (overlap + resurfacing) |
| Agents generate proposals | ✅ 3-round negotiation |
| Validator accepts/rejects | ✅ Hard + soft constraints |
| Before/after metrics calculated | ✅ From actual seed data |
| Valid schedule approvable | ✅ Score 94/100, approved |
| Rejection triggers new proposal | ✅ Re-run negotiation |
| Burst-pipe event recorded | ✅ CRITICAL WO created |
| Advisory in EN + Kannada | ✅ Unicode verified |
| Critical tests executed | ✅ 19/19 passing |
| README with setup instructions | ✅ This file |
| IBM tech clearly labeled | ✅ UI shows mode, disclaimers |
| IBM Bob development evidence | ✅ Entire implementation via Bob |
