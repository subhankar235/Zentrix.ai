
# ARCHITECTURE.md

This document defines exactly how the AI Database Administrator project is structured and how every component connects. It is built directly on top of `TECHSTACK.md` and the four feature specs (Root Cause Diagnosis, Safe Simulation & Verification Sandbox, Predictive ML + Closed-Loop Optimization, Cost-to-Dollar ROI). No component below is invented beyond what those documents require.

---

## 1. System Architecture

The system has one **application database** (its own metadata/experiment store) and zero or more **connected customer databases** (the Postgres instances being monitored, which may be Neon, RDS, Supabase, or self-hosted). The backend never writes to a customer database except through the guarded Feature 2 deployment path (`CREATE INDEX CONCURRENTLY`, `ANALYZE`), and only after policy-engine approval.

### High-Level Flow

```text
User (browser)
   │
   ▼
Frontend (Next.js)
   │  REST (JSON) + SSE for live canary/forecast updates
   ▼
Backend API (FastAPI)
   │
   ├──► Auth layer (JWT, httpOnly cookie)
   │
   ├──► Services layer (per-feature business logic)
   │        │
   │        ├──► Agents (LangGraph) ──► Tools ──► Customer Postgres (read-only telemetry,
   │        │                                      guarded write for approved changes)
   │        │
   │        ├──► ML layer (LightGBM / Isolation Forest / LSTM / Bandit)
   │        │        │
   │        │        └──► MLflow (model registry/tracking)
   │        │
   │        └──► Deterministic engines (evidence computation, statistics, ROI formula)
   │
   ├──► Workers (background jobs: telemetry polling, retraining, canary monitor)
   │
   └──► Application Database (PostgreSQL/Neon) ── users, connections, telemetry history,
            experiments, model registry pointers, forecasts, ROI records
```

### Request Flow

```text
Browser → Next.js page → API client (fetch + TanStack Query)
        → FastAPI route → auth dependency → service function
        → (service calls agent / ML / deterministic engine as needed)
        → service persists/reads via SQLAlchemy/asyncpg
        → JSON response → TanStack Query cache → UI re-render
```

### Data Flow

```text
Customer Postgres (pg_stat_statements, pg_stat_activity, pg_locks, EXPLAIN, ...)
   → Telemetry Collector worker (polling, asyncpg)
   → Application Database (normalized evidence tables)
   → Feature engineering (Pandas/Polars)
   → ML models (score/predict) + Deterministic evidence engine
   → Agents (interpret, reconcile, decide)
   → API response → Frontend
```

### Agent Flow

```text
Trigger (new telemetry batch / user-initiated diagnosis / scheduled forecast)
   → Orchestrating service builds a structured evidence payload
   → LangGraph graph invoked with that payload
   → Specialist agents run (each calls only its own tools)
   → Supervisor/Policy agent reconciles outputs
   → Structured result (JSON) returned to the service layer
   → Persisted to Application Database + returned to frontend
```

Agents are **never** given raw database credentials or unrestricted SQL execution — they call typed Python tool functions (in `app/tools/`) which enforce read-only access or a fixed set of approved DDL/DML statements.

### Database Flow

* **Application Database** (PostgreSQL/Neon): stores users, connected-database credentials (encrypted), telemetry history, evidence graphs, experiments, model metadata, forecasts, bandit state, ROI records.
* **Customer Database** (Postgres, any provider): read via system views/`EXPLAIN` for Features 1 and 3; read/write via HypoPG (session-local, non-persistent) and shadow-clone databases for Feature 2; a narrow, policy-approved write path for canary deployment (`CREATE INDEX CONCURRENTLY`, `ANALYZE`).
* **Shadow Databases** (ephemeral Docker Postgres containers): created per experiment, cloned from the customer database via `pg_dump`/`pg_restore`, destroyed after the experiment completes.

### Background Processing

Handled by `app/workers/`, run as separate async processes (not inside the request/response cycle):

* `telemetry_collector.py` — polls each connected customer database on a schedule (1–5 min).
* `retrain_worker.py` — retrains L1/L2 models and the RCA classifier when enough new labeled experiments exist.
* `canary_monitor.py` — watches an active canary deployment window and triggers rollback if thresholds are breached.
* `shadow_lab_worker.py` — provisions/tears down shadow DB containers for Feature 2 experiments.

### Authentication

FastAPI issues a JWT access token on login, set as an httpOnly, secure cookie. Every protected route depends on `get_current_user` (in `app/core/security.py`), which verifies the token and loads the user. Connected-database credentials are stored encrypted at rest in the application database (see §7) and are only decrypted server-side inside the collector/worker processes — never sent to the frontend.

### External Integrations

* **Customer PostgreSQL/Neon instance** — the only required external integration; connected via `asyncpg` using the connection string the user provides.
* **MLflow tracking server** — internal service (self-hosted via Docker), not third-party SaaS.
* No third-party LLM/model API is required to be paid; any locally-run or already-available LLM can sit behind the `app/agents/` LLM client interface.

### Real-Time Communication

* **SSE (Server-Sent Events)** from `GET /api/v1/experiments/{id}/canary/stream` and `GET /api/v1/forecasts/{id}/stream` — used only where the UI genuinely needs live updates (canary monitoring window, long-running shadow experiments). This is the single real-time mechanism used in the project; no WebSocket layer is introduced because nothing requires bidirectional client→server streaming.
* Everything else (dashboard lists, diagnosis reports, ROI numbers) uses plain REST + TanStack Query polling/refetch, which is sufficient and simpler.

---

## 2. Project Structure

```text
project-root/
├── apps/
│   ├── backend/          # FastAPI application, agents, ML, workers
│   └── frontend/         # Next.js dashboard application
├── infra/
│   ├── docker/           # Dockerfiles + docker-compose service definitions
│   └── monitoring/       # MLflow + Evidently configuration
├── docs/
│   ├── PRD.md
│   ├── TECHSTACK.md
│   └── ARCHITECTURE.md
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

* **`apps/backend/`** — everything from the API to agents, ML, and background workers. See §4.
* **`apps/frontend/`** — the Next.js dashboard. See §5.
* **`infra/`** — Docker Compose service definitions and MLflow/Evidently configuration. See §6.
* **`docs/`** — the three project reference documents (this file plus the PRD and tech stack).
* No `packages/` directory is included: the backend (Python) and frontend (TypeScript) are decoupled purely through the REST/OpenAPI contract, so there is no shared-code package to maintain. If a generated-types package becomes useful later (`openapi-typescript` output), it can be added without restructuring anything above.

---

## 3. Root Structure

```text
project-root/
├── apps/
├── infra/
├── docs/
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

| Item | Purpose | Contains | Depended on by |
|---|---|---|---|
| `apps/` | Houses the two deployable applications | `backend/`, `frontend/` | `docker-compose.yml`, CI/CD |
| `infra/` | Local/dev infrastructure definitions | Dockerfiles, MLflow config, Evidently config | `docker-compose.yml` |
| `docs/` | Source-of-truth project documents | PRD, tech stack, this architecture doc | Onboarding, planning, this doc's own cross-references |
| `.env.example` | Documents every required environment variable (no real values) | Keys for backend DB URL, JWT secret, MLflow URI, encryption key, frontend API base URL | `apps/backend/.env`, `apps/frontend/.env.local`, `docker-compose.yml` |
| `.gitignore` | Prevents committing secrets, build artifacts, virtualenvs, `node_modules`, model artifacts | Standard Python/Node/Docker ignores | Git itself |
| `docker-compose.yml` | Single command to run the whole stack locally: app DB, backend, frontend, MLflow, shadow-DB template | Service definitions referencing `infra/docker/*` | Local development, demo environment |
| `README.md` | Entry point for a new developer | Setup steps, how to run `docker-compose up`, links into `docs/` | Nothing depends on it; it depends on everything else being accurate |

---

## 4. Backend Architecture

```text
apps/backend/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── auth.py
│   │   │   ├── connections.py
│   │   │   ├── diagnostics.py
│   │   │   ├── experiments.py
│   │   │   ├── forecasts.py
│   │   │   └── roi.py
│   │   ├── deps.py
│   │   └── router.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── logging.py
│   ├── models/
│   │   ├── user.py
│   │   ├── connection.py
│   │   ├── telemetry.py
│   │   ├── experiment.py
│   │   ├── diagnosis.py
│   │   ├── forecast.py
│   │   └── roi.py
│   ├── schemas/
│   │   └── (one Pydantic schema module per model above)
│   ├── services/
│   │   ├── diagnosis_service.py
│   │   ├── simulation_service.py
│   │   ├── forecast_service.py
│   │   └── roi_service.py
│   ├── agents/
│   │   ├── graph_diagnosis.py
│   │   ├── graph_simulation.py
│   │   ├── graph_forecast.py
│   │   └── llm_client.py
│   ├── ml/
│   │   ├── anomaly/          # Isolation Forest
│   │   ├── temporal/         # LSTM autoencoder
│   │   ├── rca_classifier/   # LightGBM multi-label classifier
│   │   ├── delta_predictor/  # LightGBM outcome-delta model (Feature 2 + 3 L2)
│   │   ├── forecasting/      # LightGBM + conformal prediction (Feature 3 L1)
│   │   └── bandit/           # Contextual Thompson Sampling (Feature 3 L3)
│   ├── tools/
│   │   ├── pg_introspection.py   # pg_stat_* / pg_locks / EXPLAIN wrappers
│   │   ├── hypopg_tool.py
│   │   ├── shadow_db_tool.py
│   │   └── policy_engine.py
│   ├── workers/
│   │   ├── telemetry_collector.py
│   │   ├── retrain_worker.py
│   │   ├── canary_monitor.py
│   │   └── shadow_lab_worker.py
│   ├── db/
│   │   ├── session.py         # application DB engine/session
│   │   └── customer_db.py     # per-connection asyncpg pool manager
│   └── main.py
├── tests/
├── migrations/                # Alembic
├── Dockerfile
└── requirements.txt
```

### What each part does

* **`api/routes/`** — one file per feature area; each route function only validates input, calls a service, and returns the service's result. No business logic here.
* **`api/deps.py`** — shared FastAPI dependencies: `get_current_user`, `get_db_session`, `get_customer_connection`.
* **`core/config.py`** — loads and validates environment variables (Pydantic Settings).
* **`core/security.py`** — JWT creation/verification, password hashing, connection-string encryption/decryption.
* **`core/logging.py`** — structured logging setup used by every layer.
* **`models/`** — SQLAlchemy models for the **application database only**. Customer databases have no ORM models; they are accessed through raw introspection queries in `tools/pg_introspection.py`.
* **`schemas/`** — Pydantic request/response schemas, one-to-one with routes, used for OpenAPI generation and frontend type generation.
* **`services/`** — the orchestration layer: each service function implements one feature's end-to-end logic (e.g., `diagnosis_service.run_diagnosis()` pulls telemetry, invokes `agents/graph_diagnosis.py`, persists the result). Services are what routes call.
* **`agents/`** — LangGraph graph definitions, one per feature (diagnosis, simulation, forecast/closed-loop). `llm_client.py` is the single abstraction point for whichever LLM is configured, so agents never talk to a provider SDK directly.
* **`ml/`** — training and inference code for every model named in `TECHSTACK.md`. Each subfolder has `train.py`, `predict.py`, and `features.py`. Trained artifacts are versioned in MLflow, not committed to git.
* **`tools/`** — the only code allowed to touch a customer Postgres connection or execute SQL against it. `pg_introspection.py` is read-only. `hypopg_tool.py` creates/drops hypothetical indexes inside a transaction. `shadow_db_tool.py` clones/destroys shadow containers. `policy_engine.py` is the deterministic rule evaluator that gates canary deployment — it has no LLM involvement.
* **`workers/`** — long-running or scheduled background processes, started as separate containers/processes from the API (see §6).
* **`db/session.py`** — application DB engine (SQLAlchemy + asyncpg).
* **`db/customer_db.py`** — manages one connection pool per connected customer database, keyed by connection ID, with credentials decrypted just-in-time.
* **`migrations/`** — Alembic migrations for the application database schema only.

### Backend Request Flow

```text
API Route → Service → Agent/Business Logic → Tool → Database/External API → Response
```

Concretely, for a diagnosis request:

```text
POST /api/v1/connections/{id}/diagnose
  → diagnostics.py route
  → diagnosis_service.run_diagnosis(connection_id)
  → pulls recent evidence from app DB (already collected by telemetry_collector worker)
  → invokes agents/graph_diagnosis.py (LangGraph)
       → Planner / Concurrency / Vacuum / IO / Index agents call tools/pg_introspection.py
       → Supervisor agent reconciles → root-cause report
  → diagnosis_service persists report to app DB (models/diagnosis.py)
  → route returns schemas.DiagnosisReport
```

### Backend Layers

* **API layer** — HTTP contract only (validation, status codes, auth enforcement).
* **Authentication** — JWT verification, connection-credential encryption; lives in `core/security.py`, enforced via `api/deps.py`.
* **Business logic / Services** — the only layer allowed to coordinate multiple sub-systems (agents, ML, DB, tools) for one feature.
* **Agents** — LLM-driven reasoning over pre-computed evidence; never a source of truth for numbers.
* **ML** — deterministic-in-inference, trained offline; called synchronously by services or asynchronously by workers.
* **Tools** — the sole boundary to customer Postgres and to shadow databases; enforces read-only vs. approved-write access.
* **Database** — SQLAlchemy models/migrations for the app DB; raw asyncpg for customer DB introspection.
* **Workers** — background/scheduled processes, decoupled from the request cycle.
* **Configuration** — centralized in `core/config.py`, sourced from environment variables only.
* **Logging** — structured logs from every layer via `core/logging.py`; no separate logging service is introduced (out of scope for the hackathon build).

---

## 5. Frontend Architecture

```text
apps/frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   └── signup/
│   ├── dashboard/
│   ├── connections/
│   ├── diagnostics/
│   │   └── [connectionId]/
│   ├── experiments/
│   │   └── [experimentId]/
│   ├── forecasts/
│   │   └── [connectionId]/
│   └── roi/
├── components/
│   ├── ui/                 # generic building blocks (buttons, cards, tables)
│   └── charts/              # evidence-graph, calibration chart, MAE chart
├── features/
│   ├── diagnosis/
│   ├── simulation/
│   ├── forecasting/
│   └── roi/
├── hooks/
├── lib/
│   ├── api-client.ts
│   └── sse-client.ts
├── services/
│   └── (one API-wrapper module per feature, calling lib/api-client.ts)
├── stores/
│   └── auth-store.ts        # Zustand
├── types/
│   └── (generated from backend OpenAPI schema)
├── public/
├── tests/
└── package.json
```

### What each part does

* **`app/`** — Next.js App Router pages. `(auth)/` holds login/signup, unauthenticated. `dashboard/` is the anomaly overview. `connections/` is the "Connect Database" flow described in the PRD workflow. `diagnostics/[connectionId]/` shows Feature 1's root-cause reports and evidence graph. `experiments/[experimentId]/` shows Feature 2's simulation results, skeptic findings, and live canary panel. `forecasts/[connectionId]/` shows Feature 3's forecast timeline, calibration, and bandit view. `roi/` shows Feature 4's dollar figures.
* **`components/ui/`** — presentational, feature-agnostic components.
* **`components/charts/`** — the evidence-graph (React Flow), calibration chart, and MAE-over-iterations chart, reused across feature pages.
* **`features/*`** — feature-scoped components + hooks that are not generic enough for `components/`, mirroring the four backend feature areas one-to-one.
* **`hooks/`** — cross-feature hooks (`useAuth`, `usePolling`, `useSSE`).
* **`lib/api-client.ts`** — a single typed `fetch` wrapper (base URL, auth header/cookie handling, error normalization); every `services/` module goes through this.
* **`lib/sse-client.ts`** — thin wrapper around `EventSource` for the two SSE endpoints (canary monitor, forecast stream).
* **`services/`** — one module per feature (`diagnosisService.ts`, `simulationService.ts`, `forecastService.ts`, `roiService.ts`), each exposing typed functions that call the backend routes in §4.
* **`stores/auth-store.ts`** — Zustand store holding the logged-in user; chosen as the single state-management library because it is minimal and sufficient — no Redux is introduced.
* **`types/`** — TypeScript types generated from the backend's OpenAPI schema, keeping frontend/backend contracts in sync without a shared package.
* Server state (telemetry lists, diagnosis reports, experiment results, forecasts) is managed by **TanStack Query**, not by a global store — it owns caching, refetching, and loading/error states for every API call.

### Frontend Flow

```text
Page (app/.../page.tsx)
  → Feature component (features/<feature>/...)
  → Hook (TanStack Query hook wrapping services/<feature>Service.ts)
  → api-client.ts (fetch) or sse-client.ts (EventSource)
  → Backend route
  → Response
  → TanStack Query cache update
  → UI re-render
```

Authentication: on login, the backend sets an httpOnly JWT cookie; `auth-store.ts` holds only the non-sensitive user profile fetched from `/api/v1/auth/me` on app load. Protected routes are guarded by a Next.js middleware that checks for the presence of a valid session (via a lightweight server-side call), redirecting to `/login` if absent.

Real-time updates: the canary-monitoring panel (Feature 2) and the active-forecast panel (Feature 3) subscribe via `sse-client.ts` to the backend's SSE endpoints; every other view uses TanStack Query polling/refetch-on-focus, which is sufficient for dashboard-style data.

---

## 6. Infrastructure Architecture

```text
infra/
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── worker.Dockerfile
│   └── shadow-db.Dockerfile
└── monitoring/
    ├── mlflow.env
    └── evidently.config.yaml
```

No Kubernetes and no Terraform are introduced — the project's scope (a hackathon-grade full-stack app with background workers and a self-hosted MLflow instance) is fully covered by Docker Compose. If production scaling is needed later, `infra/kubernetes/` can be added without changing anything in `apps/`.

* **`docker/backend.Dockerfile`** — builds the FastAPI app image; runs `uvicorn app.main:app`.
* **`docker/frontend.Dockerfile`** — builds the Next.js production image.
* **`docker/worker.Dockerfile`** — shared image for `telemetry_collector`, `retrain_worker`, `canary_monitor`, `shadow_lab_worker`; the specific worker to run is selected by a command/entrypoint argument, avoiding four near-duplicate images.
* **`docker/shadow-db.Dockerfile`** — plain Postgres image with the extensions the project needs (`pg_stat_statements`, `hypopg`) pre-installed; used by `shadow_lab_worker.py` to spin up ephemeral shadow databases per experiment.
* **`monitoring/mlflow.env`** — configuration for the self-hosted MLflow tracking server container (backing store = application Postgres, artifact store = local volume).
* **`monitoring/evidently.config.yaml`** — drift-check configuration consumed by `retrain_worker.py`.

### Deployment Architecture

```text
Internet
   ↓
Frontend (Next.js container)
   ↓  REST/SSE
Backend (FastAPI container)
   ↓                              ↘
Application Database (Postgres/Neon)   Customer Database (Postgres/Neon, user-provided)
   ↑
Workers (telemetry_collector, retrain_worker, canary_monitor, shadow_lab_worker)
   ↓
MLflow (tracking server container) + Shadow DB containers (ephemeral)
```

**Environment configuration:** each service reads its variables from the root `.env` (via `docker-compose.yml`'s `env_file`), never hardcoded.
**Networking:** all containers share a single Docker Compose network; only `frontend` and `backend` publish ports to the host/Internet; the application database, MLflow, and shadow DBs are internal-only.
**Secrets:** the JWT signing key and the customer-connection encryption key are supplied as environment variables (see §11), never committed; connection strings for customer databases are encrypted before being stored in the application database.
**Scaling:** out of scope for the hackathon build — a single instance of each service is assumed; the worker image is designed so any individual worker can be scaled independently later by running more containers from the same image with a different entrypoint argument.
**Monitoring:** MLflow covers model-level monitoring; Evidently covers data/prediction drift. No separate infra-level monitoring stack (Prometheus/Grafana) is included — marked `TBD` if needed post-hackathon.

---

## 7. Database Architecture

### Application Database (PostgreSQL/Neon)

This is the system's own database, hosted on Neon (or any Postgres). It stores:

* `users` — accounts, hashed passwords.
* `connections` — encrypted connection strings + metadata for each customer database the user has connected.
* `telemetry_*` — normalized evidence collected by `telemetry_collector.py` (query metrics, table metrics, plan metrics — as specified in the feature docs).
* `diagnoses` — Feature 1 root-cause reports and evidence graphs.
* `experiments` — Feature 2 optimization experiments (baseline/candidate metrics, statistical results, skeptic findings, verdicts).
* `forecasts` / `bandit_events` / `model_predictions` — Feature 3 forecasting and closed-loop learning records.
* `roi_records` — Feature 4 dollar-savings calculations.
* MLflow's own backing tables (tracking metadata) also live in this same Postgres instance, in a separate schema.

### Customer/Connected Database (PostgreSQL, any provider incl. Neon)

The database being monitored. The backend never assumes it is Neon — it only requires standard Postgres system views and, for Feature 2, the ability to install the `hypopg` extension and to be cloned into a shadow container. No ORM models exist for this database; access is exclusively through `app/tools/pg_introspection.py`, `hypopg_tool.py`, and `shadow_db_tool.py`.

### Database Access Layer

* Application DB: SQLAlchemy (async) models in `app/models/`, sessions from `app/db/session.py`, migrations via Alembic in `apps/backend/migrations/`.
* Customer DB: raw `asyncpg` queries in `app/tools/`, connection pools managed per-connection-id by `app/db/customer_db.py`, credentials decrypted just before use and never logged.

### Read/Write Boundaries

* Customer DB reads: unrestricted for the fixed set of system views/`EXPLAIN` used by Features 1 and 3.
* Customer DB writes: restricted to (a) HypoPG hypothetical index creation (session-local, never persisted), (b) the shadow clone (a separate database entirely), and (c) the single approved canary action (`CREATE INDEX CONCURRENTLY`, `ANALYZE`) — gated by `tools/policy_engine.py` and requiring prior user approval recorded in `experiments`.
* Application DB: standard read/write from services; workers write telemetry and experiment outcomes; no customer-facing code writes directly to it except through services.

### Database Security

* Customer connection strings encrypted at rest (Fernet/AES via `core/security.py`), decrypted only in-process.
* Application DB accessed only from backend/worker containers, never from the frontend.
* Customer DB roles: the connection the user supplies should be read-only for Features 1/3; the canary write path uses the same connection but only ever issues the two whitelisted, policy-approved statement types.

---

## 8. AI / Agent Architecture

```text
Orchestrator (per-feature LangGraph graph, built in app/agents/)
├── graph_diagnosis.py  (Feature 1)
│   ├── Planner Intelligence Agent
│   ├── Concurrency Agent
│   ├── Vacuum Agent
│   ├── I/O / Buffer Agent
│   ├── Schema / Index Agent
│   └── Supervisor Agent
├── graph_simulation.py (Feature 2)
│   ├── Experiment Agent
│   ├── ML Scientist Agent
│   ├── Skeptic Agent
│   ├── Verification Agent
│   ├── Policy Agent
│   └── Deployment Agent
└── graph_forecast.py    (Feature 3)
    ├── Forecasting/Planning Agent
    └── Learning Agent
```

| Agent | Responsibility | Inputs | Tools | Models | Output | Talks to |
|---|---|---|---|---|---|---|
| Planner Intelligence | Plan regression, cardinality error, stats freshness | Query fingerprint, plan history | `pg_introspection.get_explain_plan/get_pg_stats/compare_plan` | RCA classifier (LightGBM) | Hypothesis + confidence | Supervisor |
| Concurrency | Lock chains, blocking, idle transactions | `pg_locks`/`pg_stat_activity` data | `pg_introspection.get_pg_activity/get_pg_locks` | — | Hypothesis + confidence | Supervisor |
| Vacuum | Dead-tuple ratio, bloat, autovacuum lag | `pg_stat_user_tables`, vacuum progress | `pg_introspection.get_vacuum_progress` | — | Hypothesis + confidence | Supervisor |
| I/O / Buffer | Cache eviction, temp spill, WAL pressure | Buffer/IO stats | `pg_introspection.get_buffer_stats/get_io_stats` | — | Hypothesis + confidence | Supervisor |
| Schema / Index | Missing/unused/redundant indexes | Index usage stats | `pg_introspection.get_indexes/get_index_usage` | — | Hypothesis + confidence | Supervisor |
| Supervisor (Diagnosis) | Reconcile all hypotheses into one report | All specialist outputs | — | — | Root-cause report + validation plan | `diagnosis_service` |
| Experiment | Run shadow experiment | Candidate spec | `shadow_db_tool`, `hypopg_tool` | — | Raw baseline/candidate metrics | ML Scientist, Verification |
| ML Scientist | Interpret model prediction, decide if more data needed | Delta-predictor output | — | Delta Predictor (LightGBM) | Confidence assessment | Experiment, Verification |
| Skeptic | Actively search for regressions | Baseline/candidate metrics | `pg_introspection` (regression queries) | — | List of red flags | Verification |
| Verification | Combine stats + ML + skeptic into a verdict | All of the above | — | — | VERIFIED / CONDITIONAL / REJECTED | Policy Agent |
| Policy | Deterministic go/no-go rules | Verification verdict | `policy_engine.py` | — | Approve/Block canary | Deployment Agent |
| Deployment | Execute approved change, run canary, rollback if needed | Approved candidate | `pg_introspection` (canary write path) | — | Deployment result | `simulation_service`, `canary_monitor` worker |
| Forecasting/Planning | Decide if degradation risk warrants action | Forecast model output | — | Forecasting model (LightGBM), Bandit | Trigger for Feature 2 simulation | `graph_simulation.py`, `forecast_service` |
| Learning | Log outcomes, trigger retraining, promote models | Experiment outcome vs. prediction | — | — | Updated model registry entry | `retrain_worker`, MLflow |

All agent code lives in `apps/backend/app/agents/`; every tool an agent can call lives in `apps/backend/app/tools/`; every model an agent consults lives in `apps/backend/app/ml/`. Agents are stateless per invocation — state (evidence, experiment history, bandit state) is always read from and written back to the application database, never held in agent memory across requests.

---

## 9. Feature → Code Mapping

| Feature | Frontend Location | Backend Location | Agent/ML | Database | Infrastructure |
|---|---|---|---|---|---|
| Feature 1 — Root Cause Diagnosis | `app/diagnostics/[connectionId]/`, `features/diagnosis/`, `components/charts/` (evidence graph) | `api/routes/diagnostics.py`, `services/diagnosis_service.py`, `tools/pg_introspection.py`, `workers/telemetry_collector.py` | `agents/graph_diagnosis.py` (5 specialists + Supervisor); `ml/anomaly/` (Isolation Forest), `ml/temporal/` (LSTM autoencoder), `ml/rca_classifier/` (LightGBM) | `models/telemetry.py`, `models/diagnosis.py` (app DB); read-only access to customer DB | `docker/worker.Dockerfile` (collector) |
| Feature 2 — Safe Simulation & Verification | `app/experiments/[experimentId]/`, `features/simulation/` | `api/routes/experiments.py`, `services/simulation_service.py`, `tools/hypopg_tool.py`, `tools/shadow_db_tool.py`, `tools/policy_engine.py`, `workers/shadow_lab_worker.py`, `workers/canary_monitor.py` | `agents/graph_simulation.py` (Experiment, ML Scientist, Skeptic, Verification, Policy, Deployment); `ml/delta_predictor/` (LightGBM) | `models/experiment.py` (app DB); shadow-clone customer DB; guarded write path on customer DB | `docker/shadow-db.Dockerfile`, `docker/worker.Dockerfile` |
| Feature 3 — Predictive ML + Closed-Loop Optimization | `app/forecasts/[connectionId]/`, `features/forecasting/`, `components/charts/` (calibration, MAE) | `api/routes/forecasts.py`, `services/forecast_service.py`, `workers/retrain_worker.py` | `agents/graph_forecast.py` (Forecasting/Planning, Learning); `ml/forecasting/` (LightGBM + conformal), `ml/delta_predictor/` (shared with Feature 2), `ml/bandit/` (Contextual Thompson Sampling) | `models/forecast.py` (app DB); DuckDB/Parquet for training data | `monitoring/mlflow.env`, `monitoring/evidently.config.yaml` |
| Feature 4 — Cost-to-Dollar ROI | `app/roi/`, `features/roi/` | `api/routes/roi.py`, `services/roi_service.py` (pure deterministic calculation, no agent/ML) | — | `models/roi.py` (app DB); reads from `experiments` table | — |

---

## 10. Communication Architecture

* **Frontend ↔ Backend:** REST over HTTPS (JSON), authenticated via an httpOnly JWT cookie; SSE for the two live-update endpoints (canary monitor, active forecast) described in §1 and §5.
* **Backend ↔ Application Database:** SQLAlchemy (async) over `asyncpg`, connection-pooled.
* **Backend ↔ Customer Database:** raw `asyncpg`, one pool per connection ID, managed by `app/db/customer_db.py`.
* **Backend ↔ Agents:** in-process function calls (LangGraph graphs are invoked directly from service functions in the same Python process — no separate agent service/queue is introduced, since nothing in the feature docs requires agents to run out-of-process).
* **Agents ↔ Tools:** in-process function calls, typed Python functions in `app/tools/`.
* **Backend ↔ External APIs:** only the customer's own Postgres endpoint and the self-hosted MLflow tracking server (internal HTTP).
* **Workers ↔ Backend:** workers and the API share the same codebase/database but run as separate processes/containers; they communicate only indirectly, through the application database (a worker writes a row, the API reads it on next request) — no message queue is introduced, since polling/scheduled workers are sufficient at this scale.
* **Services ↔ Services:** plain function calls within the backend process; `simulation_service` calls into `diagnosis_service`'s evidence only by reading the same application-database tables, not by direct cross-service calls.

---

## 11. Environment & Configuration

```text
.env.example              # documents every variable below, root of repo
apps/backend/.env         # backend-specific values, gitignored
apps/frontend/.env.local  # frontend-specific values, gitignored
infra/monitoring/mlflow.env
```

| Variable | Component | Purpose |
|---|---|---|
| `APP_DATABASE_URL` | backend, workers, migrations | Connection string to the application Postgres/Neon instance |
| `JWT_SECRET_KEY` | backend | Signs/verifies auth tokens |
| `CONNECTION_ENCRYPTION_KEY` | backend | Encrypts customer database connection strings at rest |
| `MLFLOW_TRACKING_URI` | backend, workers | Where models/experiments are logged |
| `TELEMETRY_POLL_INTERVAL_SECONDS` | `telemetry_collector` worker | Polling frequency per connected database |
| `CANARY_MONITOR_WINDOW_MINUTES` | `canary_monitor` worker | Canary observation duration before auto-commit |
| `SHADOW_DB_IMAGE` | `shadow_lab_worker` | Which Docker image to clone for shadow experiments |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | Base URL the frontend calls for REST/SSE |
| `NODE_ENV` / `ENVIRONMENT` | both | `development` / `production` switch for logging/config |

No real secret values are included anywhere in this document or in `.env.example` — only variable names and purposes.

---

## 12. Final Complete Repository Tree

```text
project-root/
├── apps/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── routes/
│   │   │   │   │   ├── auth.py
│   │   │   │   │   ├── connections.py
│   │   │   │   │   ├── diagnostics.py
│   │   │   │   │   ├── experiments.py
│   │   │   │   │   ├── forecasts.py
│   │   │   │   │   └── roi.py
│   │   │   │   ├── deps.py
│   │   │   │   └── router.py
│   │   │   ├── core/
│   │   │   │   ├── config.py
│   │   │   │   ├── security.py
│   │   │   │   └── logging.py
│   │   │   ├── models/
│   │   │   │   ├── user.py
│   │   │   │   ├── connection.py
│   │   │   │   ├── telemetry.py
│   │   │   │   ├── experiment.py
│   │   │   │   ├── diagnosis.py
│   │   │   │   ├── forecast.py
│   │   │   │   └── roi.py
│   │   │   ├── schemas/
│   │   │   │   ├── user.py
│   │   │   │   ├── connection.py
│   │   │   │   ├── telemetry.py
│   │   │   │   ├── experiment.py
│   │   │   │   ├── diagnosis.py
│   │   │   │   ├── forecast.py
│   │   │   │   └── roi.py
│   │   │   ├── services/
│   │   │   │   ├── diagnosis_service.py
│   │   │   │   ├── simulation_service.py
│   │   │   │   ├── forecast_service.py
│   │   │   │   └── roi_service.py
│   │   │   ├── agents/
│   │   │   │   ├── graph_diagnosis.py
│   │   │   │   ├── graph_simulation.py
│   │   │   │   ├── graph_forecast.py
│   │   │   │   └── llm_client.py
│   │   │   ├── ml/
│   │   │   │   ├── anomaly/
│   │   │   │   │   ├── train.py
│   │   │   │   │   └── predict.py
│   │   │   │   ├── temporal/
│   │   │   │   │   ├── train.py
│   │   │   │   │   └── predict.py
│   │   │   │   ├── rca_classifier/
│   │   │   │   │   ├── train.py
│   │   │   │   │   └── predict.py
│   │   │   │   ├── delta_predictor/
│   │   │   │   │   ├── train.py
│   │   │   │   │   └── predict.py
│   │   │   │   ├── forecasting/
│   │   │   │   │   ├── train.py
│   │   │   │   │   └── predict.py
│   │   │   │   └── bandit/
│   │   │   │       └── policy.py
│   │   │   ├── tools/
│   │   │   │   ├── pg_introspection.py
│   │   │   │   ├── hypopg_tool.py
│   │   │   │   ├── shadow_db_tool.py
│   │   │   │   └── policy_engine.py
│   │   │   ├── workers/
│   │   │   │   ├── telemetry_collector.py
│   │   │   │   ├── retrain_worker.py
│   │   │   │   ├── canary_monitor.py
│   │   │   │   └── shadow_lab_worker.py
│   │   │   ├── db/
│   │   │   │   ├── session.py
│   │   │   │   └── customer_db.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── migrations/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── frontend/
│       ├── app/
│       │   ├── (auth)/
│       │   │   ├── login/
│       │   │   └── signup/
│       │   ├── dashboard/
│       │   ├── connections/
│       │   ├── diagnostics/
│       │   │   └── [connectionId]/
│       │   ├── experiments/
│       │   │   └── [experimentId]/
│       │   ├── forecasts/
│       │   │   └── [connectionId]/
│       │   └── roi/
│       ├── components/
│       │   ├── ui/
│       │   └── charts/
│       ├── features/
│       │   ├── diagnosis/
│       │   ├── simulation/
│       │   ├── forecasting/
│       │   └── roi/
│       ├── hooks/
│       ├── lib/
│       │   ├── api-client.ts
│       │   └── sse-client.ts
│       ├── services/
│       │   ├── diagnosisService.ts
│       │   ├── simulationService.ts
│       │   ├── forecastService.ts
│       │   └── roiService.ts
│       ├── stores/
│       │   └── auth-store.ts
│       ├── types/
│       ├── public/
│       ├── tests/
│       └── package.json
├── infra/
│   ├── docker/
│   │   ├── backend.Dockerfile
│   │   ├── frontend.Dockerfile
│   │   ├── worker.Dockerfile
│   │   └── shadow-db.Dockerfile
│   └── monitoring/
│       ├── mlflow.env
│       └── evidently.config.yaml
├── docs/
│   ├── PRD.md
│   ├── TECHSTACK.md
│   └── ARCHITECTURE.md
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

`docs/PRD.md` is marked `TBD` for file content since no standalone PRD document was provided as source material — the four feature specifications supplied so far serve as the PRD's content and should be consolidated into `docs/PRD.md` directly.
