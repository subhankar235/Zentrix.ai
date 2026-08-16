# BACKEND_STEPS.md

## Overview

This document is the step-by-step implementation roadmap for the AI Database Administrator backend (`apps/backend/`), derived directly from `PRD.md`, `TECHSTACK.md`, and `ARCHITECTURE.md`. It covers only backend work — no frontend (`apps/frontend/`) steps are included. Each step lists its goal, exact files/folders, what to implement, prerequisites, and how to verify completion.

---

## Step 1 — Backend Project Scaffolding

**Goal**
Create the base Python project structure for the FastAPI backend exactly as defined in `ARCHITECTURE.md` §4 and §12.

**Files/Folders**

```
apps/backend/
├── app/
│   ├── api/routes/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── agents/
│   ├── ml/
│   │   ├── anomaly/
│   │   ├── temporal/
│   │   ├── rca_classifier/
│   │   ├── delta_predictor/
│   │   ├── forecasting/
│   │   └── bandit/
│   ├── tools/
│   ├── workers/
│   ├── db/
│   └── main.py
├── tests/
├── migrations/
├── Dockerfile
└── requirements.txt
```

**Implementation**
Create all directories above as empty packages (`__init__.py` in each Python package folder). Create an empty `app/main.py` placeholder (FastAPI app instantiated in Step 8). Create empty `requirements.txt` (populated in Step 2).

**Dependencies**
Repo root (`project-root/`) already exists per `ARCHITECTURE.md` §2/§3 (`apps/`, `infra/`, `docs/`, `.env.example`, `.gitignore`, `docker-compose.yml`, `README.md`).

**Verification**
`apps/backend` directory tree matches `ARCHITECTURE.md` §4 exactly; `python -m app.main` (once `main.py` exists) doesn't error on import due to missing packages.

**Expected Result**
A skeleton backend package structure with zero business logic, ready for dependency installation.

---

## Step 2 — Dependencies & Package Configuration

**Goal**
Lock in all backend dependencies referenced in `TECHSTACK.md`.

**Files/Folders**

- `apps/backend/requirements.txt`
- `apps/backend/Dockerfile` (base image reference only at this stage; full build in Step 25)

**Implementation**
Add pinned versions for: `fastapi`, `uvicorn`, `asyncpg`, `sqlalchemy` (async), `pydantic`, `pydantic-settings`, `alembic`, `python-jose` or `pyjwt` (JWT — exact library TBD per `PRD.md` §24 auth mechanism TBD), `passlib`/`bcrypt` (password hashing), `cryptography` (Fernet/AES connection-string encryption per `ARCHITECTURE.md` §11), `langgraph`, `langchain-core` (or equivalent LLM client abstraction), `numpy`, `pandas`, `polars`, `scikit-learn`, `scipy`, `ruptures`, `lightgbm`, `torch` (LSTM autoencoder), `mlflow`, `evidently`, `duckdb`, `hypopg` (Postgres extension, not pip — noted as DB-level dependency), `httpx` (for MLflow/API calls), `pytest`, `pytest-asyncio`, `sse-starlette` (SSE endpoints per `ARCHITECTURE.md` §1/§10).

**Dependencies**
Step 1 complete.

**Verification**
`pip install -r requirements.txt --break-system-packages` succeeds in a clean environment.

**Expected Result**
All backend Python dependencies installable and importable.

---

## Step 3 — Environment Variables & Settings Loader

**Goal**
Define and load all environment variables per `ARCHITECTURE.md` §11.

**Files/Folders**

- `apps/backend/app/core/config.py`
- `.env.example` (root, update if missing entries)
- `apps/backend/.env` (gitignored, local only)

**Implementation**
In `core/config.py`, define a Pydantic Settings class (via `pydantic-settings`) sourcing: `APP_DATABASE_URL`, `JWT_SECRET_KEY`, `CONNECTION_ENCRYPTION_KEY`, `MLFLOW_TRACKING_URI`, `TELEMETRY_POLL_INTERVAL_SECONDS`, `CANARY_MONITOR_WINDOW_MINUTES`, `SHADOW_DB_IMAGE`, `ENVIRONMENT`. Instantiate a single cached `get_settings()` accessor. Ensure `.env.example` documents every variable name and purpose only (no real values), per `ARCHITECTURE.md` §11.

**Dependencies**
Step 2 (`pydantic-settings` installed).

**Verification**
Import `from app.core.config import get_settings` and confirm all fields load from a test `.env` without error; missing required var raises a clear validation error.

**Expected Result**
Centralized, type-validated configuration accessible to every backend layer.

---

## Step 4 — Structured Logging Setup

**Goal**
Establish the logging foundation used by every subsequent layer (`ARCHITECTURE.md` §4 "core/logging.py").

**Files/Folders**

- `apps/backend/app/core/logging.py`

**Implementation**
Configure structured (JSON or key=value) logging with a standard logger factory function (`get_logger(name)`), log level driven by `ENVIRONMENT`/config, and a consistent format including timestamp, level, module, and (later) request/agent/experiment IDs for traceability.

**Dependencies**
Step 3 (config).

**Verification**
Call `get_logger(__name__).info("test")` and confirm structured output on stdout.

**Expected Result**
Every later module can import and use a consistent logger.

---

## Step 5 — Application Database Connection Layer

**Goal**
Set up the async SQLAlchemy engine/session for the application database (PostgreSQL/Neon), per `ARCHITECTURE.md` §4 (`db/session.py`) and §7.

**Files/Folders**

- `apps/backend/app/db/session.py`

**Implementation**
Create an async SQLAlchemy engine from `settings.APP_DATABASE_URL`, a sessionmaker (`AsyncSession`), and a `get_db_session()` FastAPI dependency (async generator yielding/closing a session). Define the SQLAlchemy `Base` declarative class here or in a shared `app/db/base.py` for models to inherit from.

**Dependencies**
Step 3 (config), Step 4 (logging), a reachable application PostgreSQL instance (local Docker Postgres or Neon).

**Verification**
A simple `SELECT 1` executed through the session succeeds against the application DB.

**Expected Result**
Reusable async DB session/engine ready for ORM models.

---

## Step 6 — Application Database Models (SQLAlchemy)

**Goal**
Implement the application-database ORM models per `ARCHITECTURE.md` §4/§7 and `PRD.md` §13 Data Model.

**Files/Folders**

- `apps/backend/app/models/user.py`
- `apps/backend/app/models/connection.py`
- `apps/backend/app/models/telemetry.py`
- `apps/backend/app/models/experiment.py`
- `apps/backend/app/models/diagnosis.py`
- `apps/backend/app/models/forecast.py`
- `apps/backend/app/models/roi.py`

**Implementation**

- `user.py`: `users` table (id, email, hashed_password, created_at; RBAC/role field TBD per `PRD.md` §24).
- `connection.py`: `database_connections` (encrypted connection string, host metadata, permission-check status, SSL config, owner user_id).
- `telemetry.py`: `query_metrics`, `table_metrics`, `plan_metrics` tables with fields exactly as specified in `PRD.md` §13 and `ARCHITECTURE.md` §7.
- `experiment.py`: `optimization_experiments`, `model_predictions`, `bandit_events` (fields per `PRD.md` §13).
- `diagnosis.py`: `diagnoses`, `evidence_graph_nodes`, `evidence_graph_edges` (per `PRD.md` §13 inferred entities).
- `forecast.py`: forecast records, degradation-probability curves, calibration/drift report storage.
- `roi.py`: `roi_records` (Feature 4, fields TBD pending pricing model per `PRD.md` §5 Feature 4).
- Also add (inferred entities, `PRD.md` §13): `approvals`, `audit_log`, `deployments`/`canary_runs` — place in the most relevant existing model file or a new `app/models/audit.py` / `app/models/approval.py` (TBD final file split, but must exist before Step 19).

**Dependencies**
Step 5 (`Base`/session).

**Verification**
`from app.models import *` imports cleanly; SQLAlchemy metadata reflects all expected tables (`Base.metadata.tables.keys()`).

**Expected Result**
Complete ORM layer for the application database matching the PRD data model.

---

## Step 7 — Alembic Migrations

**Goal**
Version-control the application database schema, per `ARCHITECTURE.md` §4 (`migrations/`, Alembic).

**Files/Folders**

- `apps/backend/migrations/` (Alembic env, versions/)
- `apps/backend/alembic.ini`

**Implementation**
Initialize Alembic pointed at `APP_DATABASE_URL` and the models' metadata from Step 6. Generate the initial migration creating all tables (`users`, `connections`, `telemetry_*`, `experiments`, `model_predictions`, `bandit_events`, `diagnoses`, `evidence_graph_*`, `forecasts`, `roi_records`, `approvals`, `audit_log`, `deployments`/`canary_runs`).

**Dependencies**
Step 6 (models), Step 5 (DB connection), reachable application Postgres instance.

**Verification**
`alembic upgrade head` runs cleanly against a fresh application database; `alembic downgrade base` reverses cleanly.

**Expected Result**
Application database schema is created and reproducible via migrations.

---

## Step 8 — Authentication & Authorization Core

**Goal**
Implement JWT-based auth and connection-credential encryption per `ARCHITECTURE.md` §4 (`core/security.py`) and §10/§14.

**Files/Folders**

- `apps/backend/app/core/security.py`
- `apps/backend/app/api/deps.py`

**Implementation**
- `security.py`: password hashing (passlib/bcrypt), JWT creation/verification (issue on login, httpOnly secure cookie per `ARCHITECTURE.md` §4), and Fernet/AES encryption/decryption helpers for customer connection strings (`CONNECTION_ENCRYPTION_KEY`).
- `api/deps.py`: `get_current_user` dependency (verifies JWT cookie, loads User via `get_db_session`), `get_db_session` re-export, and `get_customer_connection` dependency stub (wired fully in Step 10).
- Note: exact RBAC scheme for who may approve production-modifying actions is TBD per `PRD.md` §10/§24 — implement a single role field on `User` now, with enforcement logic added at approval endpoints in Step 19.

**Dependencies**
Step 3 (config for `JWT_SECRET_KEY`/`CONNECTION_ENCRYPTION_KEY`), Step 6 (User, connection models).

**Verification**
Unit test: hash+verify password round-trip; encode+decode JWT round-trip; encrypt+decrypt a sample connection string round-trip.

**Expected Result**
Reusable, tested auth and encryption primitives available to all routes.

---

## Step 9 — Pydantic Schemas

**Goal**
Define request/response schemas one-to-one with models, per `ARCHITECTURE.md` §4.

**Files/Folders**

- `apps/backend/app/schemas/user.py`
- `apps/backend/app/schemas/connection.py`
- `apps/backend/app/schemas/telemetry.py`
- `apps/backend/app/schemas/experiment.py`
- `apps/backend/app/schemas/diagnosis.py`
- `apps/backend/app/schemas/forecast.py`
- `apps/backend/app/schemas/roi.py`

**Implementation**
For each model in Step 6, define `Create`, `Read`/`Out`, and (where relevant) `Update` Pydantic schemas. Include nested schemas for evidence graph nodes/edges, root-cause report structure (`primary_root_cause`, `confidence`, `contributing_causes`, `evidence`, `timeline`, `recommended_action`, `validation_plan` per `PRD.md` §5 Feature 1), and simulation/verification report structure (per `PRD.md` §5 Feature 2).

**Dependencies**
Step 6 (models to mirror).

**Verification**
Schemas validate sample JSON payloads matching the PRD's example structures (e.g., root-cause report JSON in `PRD.md`).

**Expected Result**
Typed I/O contracts ready for OpenAPI generation and frontend type generation.

---

## Step 10 — Core API Skeleton (FastAPI App + Router Wiring)

**Goal**
Stand up the FastAPI application and route registration per `ARCHITECTURE.md` §4 and `PRD.md` §12.

**Files/Folders**

- `apps/backend/app/main.py`
- `apps/backend/app/api/router.py`
- `apps/backend/app/api/routes/auth.py`
- `apps/backend/app/api/routes/connections.py`
- `apps/backend/app/api/routes/diagnostics.py`
- `apps/backend/app/api/routes/experiments.py`
- `apps/backend/app/api/routes/forecasts.py`
- `apps/backend/app/api/routes/roi.py`

**Implementation**
- `main.py`: instantiate `FastAPI()`, register `core/logging.py` startup hook, include `api/router.py`.
- `api/router.py`: aggregate all route modules under `/api/v1` prefix, per endpoint table in `PRD.md` §12.
- Each route file: stub route functions (signatures + auth dependency + `response_model` only — no business logic yet, since services don't exist until Step 11).

Endpoints to stub: `POST /connections`, `POST /connections/{id}/test`, `GET /connections/{id}/telemetry`, `GET /connections/{id}/diagnoses`, `GET /diagnoses/{id}`, `GET /diagnoses/{id}/recommendations`, `POST /recommendations/{id}/simulate`, `GET /recommendations/{id}/verification`, `POST /recommendations/{id}/approve`, `POST /recommendations/{id}/reject`, `GET /deployments/{id}`, `GET /experiments`, `GET /forecast/{connectionId}`, `GET /models/performance`, plus `auth.py` (`/auth/login`, `/auth/signup`, `/auth/me`) and the two SSE endpoints (`GET /experiments/{id}/canary/stream`, `GET /forecasts/{id}/stream`) per `ARCHITECTURE.md` §1.

**Dependencies**
Step 8 (auth deps), Step 9 (schemas).

**Verification**
`uvicorn app.main:app` starts; `GET /docs` renders OpenAPI schema listing all stubbed routes; unauthenticated requests to protected routes return 401.

**Expected Result**
A running FastAPI server exposing the full API surface (unimplemented business logic, routable and documented).

---

## Step 11 — Customer Database Connection Manager

**Goal**
Implement per-connection pooling to monitored customer Postgres databases, per `ARCHITECTURE.md` §4/§7 (`db/customer_db.py`).

**Files/Folders**

- `apps/backend/app/db/customer_db.py`

**Implementation**
A connection-pool manager keyed by `connection_id`: decrypts the stored connection string just-in-time (using `core/security.py`), opens an asyncpg pool, caches pools per connection ID, and exposes `get_customer_pool(connection_id)`. Wire `api/deps.py`'s `get_customer_connection` dependency to this manager. Never logs decrypted credentials (per `ARCHITECTURE.md` §14 / `PRD.md` §14).

**Dependencies**
Step 8 (encryption), Step 6 (connection model), Step 5 (app DB to look up connection metadata).

**Verification**
Integration test: store an encrypted test Postgres connection string, retrieve a pool, run `SELECT 1` against a real test Postgres instance.

**Expected Result**
Backend can safely open read-only connections to any user-registered monitored database.

---

## Step 12 — Connection Onboarding Service (Test & Permission Check)

**Goal**
Implement the "Connect Database" workflow business logic per `TECHSTACK.md` User Connection Workflow and `PRD.md` §4 Core User Journey.

**Files/Folders**

- `apps/backend/app/services/connection_service.py` (new — supports connections.py routes; add to `ARCHITECTURE.md`'s services layer)
- Update `apps/backend/app/api/routes/connections.py`

**Implementation**
`connection_service.py`: `create_connection()` (encrypt + persist), `test_connection()` (verify reachability, credentials, required extension `pg_stat_statements`, required permission level — read-only role check), `list_telemetry_summary()`. Wire these into the `connections.py` route handlers from Step 10.

**Dependencies**
Step 11 (customer_db pool manager), Step 6 (connection model), Step 9 (connection schemas).

**Verification**
`POST /connections` + `POST /connections/{id}/test` against a real test Postgres instance returns success with permission/extension status; a database missing `pg_stat_statements` returns a clear failure reason.

**Expected Result**
Users can register and validate a monitored database connection end-to-end.

---

## Step 13 — PostgreSQL Introspection Tools (Read-Only)

**Goal**
Build the sole boundary code allowed to run introspection queries against monitored databases, per `ARCHITECTURE.md` §4 (`tools/pg_introspection.py`) and `TECHSTACK.md` Feature 1/2 telemetry sources.

**Files/Folders**

- `apps/backend/app/tools/pg_introspection.py`

**Implementation**
Typed async functions wrapping read-only queries against: `pg_stat_statements`, `pg_stat_activity`, `pg_locks`, `pg_wait_events`, `pg_stat_user_tables`, `pg_stat_user_indexes`, `pg_stats`, `pg_stat_progress_vacuum`, `pg_statio_user_tables`, `pg_statio_user_indexes`, and `EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON)`.

Functions named per `ARCHITECTURE.md` §8 tool list: `get_explain_plan`, `get_plan_history`, `get_pg_stats`, `get_table_statistics`, `compare_plan`, `calculate_cardinality_error`, `get_pg_activity`, `get_pg_locks`, `get_wait_events`, `build_lock_graph`, `get_table_stats`, `get_vacuum_progress`, `get_autovacuum_history`, `estimate_bloat`, `get_dead_tuple_ratio`, `get_buffer_stats`, `get_io_stats`, `get_explain_buffers`, `get_temp_file_stats`, `get_wal_stats`, `get_indexes`, `get_index_usage`, `get_table_schema`, `get_constraints`, `get_query_plan`.

Each returns structured Python objects/dicts — raw EXPLAIN JSON is parsed into features here (never passed raw to the LLM, per `PRD.md` §8).

**Dependencies**
Step 11 (customer_db pool manager).

**Verification**
Unit/integration tests against a seeded test Postgres instance confirm each function returns expected structured output for known fixture data.

**Expected Result**
A complete, reusable read-only introspection toolkit that all Feature 1/3 agents will call.

---

## Step 14 — Telemetry Collector Worker

**Goal**
Implement continuous read-only polling and normalized storage, per `ARCHITECTURE.md` §4/§6 and `PRD.md` §19 MVP item 2.

**Files/Folders**

- `apps/backend/app/workers/telemetry_collector.py`

**Implementation**
A scheduled async worker (loop with `TELEMETRY_POLL_INTERVAL_SECONDS` interval) that, per connected database: calls `tools/pg_introspection.py` functions, normalizes results into `query_metrics`, `table_metrics`, `plan_metrics` rows, and writes them to the application DB via `db/session.py`. Runs as a separate process/container (per `ARCHITECTURE.md` §6 `worker.Dockerfile`), not inside the request cycle.

**Dependencies**
Step 13 (introspection tools), Step 6 (telemetry models), Step 5 (app DB session).

**Verification**
Run the worker against a test connection for several poll cycles; confirm `query_metrics`/`table_metrics`/`plan_metrics` rows accumulate correctly in the application DB.

**Expected Result**
Continuous, working telemetry ingestion pipeline — the evidence foundation for every downstream feature.

---

## Step 15 — Deterministic Evidence Engine

**Goal**
Implement the non-ML evidence computation layer per `ARCHITECTURE.md` §1 ("Deterministic engines") and `PRD.md` §5 Feature 1.

**Files/Folders**

- `apps/backend/app/services/evidence_engine.py` (new; deterministic computation service, separate from ML)

**Implementation**
Functions for: plan diffing (`plan_hash` comparison, PLAN_FLIP detection), cardinality error calculation (`log(actual_rows+1) - log(estimated_rows+1)`), lock-graph construction from `pg_locks`/`pg_stat_activity` data, vacuum/bloat metrics (`dead_tuple_ratio`, `vacuum_age`, `analyze_age`, `autovacuum_lag`, growth rates). No model involvement — pure computation over telemetry rows.

**Dependencies**
Step 14 (telemetry rows to compute over), Step 13 (introspection tool output format).

**Verification**
Unit tests with fixture telemetry rows produce expected cardinality-error values, correct PLAN_FLIP detection, and correct lock-graph edges.

**Expected Result**
A tested, deterministic evidence layer independent of any ML model — the credibility foundation called out in `PRD.md` §19 MVP item 3.

---

## Step 16 — ML Layer: Anomaly Detection & Root-Cause Classifier (Feature 1)

**Goal**
Implement Feature 1's ML models per `TECHSTACK.md`/`ARCHITECTURE.md` §4/§8.

**Files/Folders**

- `apps/backend/app/ml/anomaly/train.py`
- `apps/backend/app/ml/anomaly/predict.py`
- `apps/backend/app/ml/anomaly/features.py`
- `apps/backend/app/ml/temporal/train.py`
- `apps/backend/app/ml/temporal/predict.py`
- `apps/backend/app/ml/temporal/features.py`
- `apps/backend/app/ml/rca_classifier/train.py`
- `apps/backend/app/ml/rca_classifier/predict.py`
- `apps/backend/app/ml/rca_classifier/features.py`

**Implementation**
- `anomaly/`: Isolation Forest (scikit-learn) over the ~17-feature multivariate vector per `TECHSTACK.md`, plus robust Z-score as interpretability layer.
- `temporal/`: LSTM autoencoder (PyTorch) over 30–60 min windows for next-window anomaly probability.
- `rca_classifier/`: LightGBM multi-label classifier over plan/telemetry features predicting the fault classes listed in `PRD.md` §7 (`STALE_STATISTICS`, `PLAN_FLIP`, etc.), plus a separate causal-ranking step (`PRIMARY`/`CONTRIBUTING`/`CORRELATED`/`UNRELATED`).

All `train.py` scripts log runs/artifacts to MLflow (`MLFLOW_TRACKING_URI`); `predict.py` modules load the latest promoted model version and expose a `predict(features) -> result` function for services/agents to call. Training data source: Database Fault Laboratory (Step 16b below).

**Dependencies**
Step 15 (evidence engine, feature source), Step 3 (`MLFLOW_TRACKING_URI` config).

**Verification**
`train.py` runs on fixture/lab-generated data and produces a model artifact logged to MLflow; `predict.py` returns valid probability outputs on held-out sample data.

**Expected Result**
Working anomaly-scoring and root-cause classification models available for agent consumption.

---

## Step 16b — Database Fault Laboratory (Training Data Generator)

**Goal**
Build the self-generated training-data pipeline required by Step 16, per `PRD.md` §7/§19 and `ARCHITECTURE.md` note in `TECHSTACK.md`.

**Files/Folders**

- `apps/backend/app/ml/rca_classifier/fault_lab/` (new subpackage: `injector.py`, `workload_gen.py`, `ground_truth_recorder.py`)
- `infra/docker/` (referenced Docker Postgres instance for the lab; see Step 25)

**Implementation**
A Dockerized Postgres + pgbench-based workload generator + fault injector implementing the fault matrix from `PRD.md` §7 (stale statistics, plan regression, cardinality misestimation, lock contention, vacuum starvation, index problems, I/O/buffer pressure), each recording a ground-truth label alongside collected telemetry (via Step 13's introspection tools) into a structured dataset file/table consumed by `rca_classifier/train.py`.

**Dependencies**
Step 13 (introspection tools reused against the lab database), Step 14 (collector reused/adapted for lab telemetry capture).

**Verification**
Run one full fault-injection scenario end-to-end; confirm a labeled experiment record is produced matching the schema in `PRD.md` §7 example JSON.

**Expected Result**
A repeatable generator producing labeled training data for the RCA classifier (and reusable structure for Feature 2/3 labs in later steps).

---

## Step 17 — Agent Tooling Boundary Review (Read-Only Enforcement)

**Goal**
Confirm and lock down the agent/tool boundary per `ARCHITECTURE.md` §1/§8 ("Agents are never given raw database credentials or unrestricted SQL execution").

**Files/Folders**

- `apps/backend/app/tools/pg_introspection.py` (audit, no new file)
- `apps/backend/app/tools/policy_engine.py` (scaffold only — full logic in Step 22)

**Implementation**
Verify every function in `tools/pg_introspection.py` is strictly read-only (no DDL/DML). Create the `policy_engine.py` module stub now (empty rule-evaluation interface) so Feature 2's agents (Step 20) can reference it without circular dependency later.

**Dependencies**
Step 13.

**Verification**
Static review / grep confirms no write statements in `pg_introspection.py`; `policy_engine.py` importable with a placeholder `evaluate()` function.

**Expected Result**
A verified, hardened read-only tool boundary before any agent code is written.

---

## Step 18 — LLM Client Abstraction & Feature 1 Agent Graph

**Goal**
Implement the LangGraph-based diagnosis agents per `ARCHITECTURE.md` §8 and `PRD.md` §6.

**Files/Folders**

- `apps/backend/app/agents/llm_client.py`
- `apps/backend/app/agents/graph_diagnosis.py`

**Implementation**
- `llm_client.py`: single abstraction point for whichever LLM is configured (provider TBD per `TECHSTACK.md` note — "any open-weight or already-available LLM"); exposes a uniform `complete(prompt, ...)`/`structured_complete(...)` interface so agents never call a provider SDK directly.
- `graph_diagnosis.py`: LangGraph graph wiring the five specialist agents (Planner Intelligence, Concurrency, Vacuum, I/O/Buffer, Schema/Index) — each scoped to its tool subset from `ARCHITECTURE.md` §8 table — plus the Supervisor Agent implementing the contradiction-reconciliation protocol (earliest-explaining hypothesis wins, evidence directness weighted over correlation; unresolved → UNKNOWN with all hypotheses shown, per `PRD.md` §5 Feature 1 Failure cases). Agents call `tools/pg_introspection.py` (read-only) and `ml/rca_classifier/predict.py`, `ml/anomaly/predict.py`.

**Dependencies**
Step 13 (tools), Step 16 (ML predict functions), Step 17 (boundary confirmed).

**Verification**
Invoke `graph_diagnosis.py` with a fixture evidence payload; confirm each specialist agent produces a hypothesis+confidence, and the Supervisor produces a structured root-cause report matching the JSON shape in `PRD.md` §5.

**Expected Result**
A working, testable multi-agent diagnosis pipeline (Feature 1's AI core).

---

## Step 19 — Diagnosis Service & API Wiring (Feature 1 Complete)

**Goal**
Connect the diagnosis agent graph to the API layer, per `ARCHITECTURE.md` §4 Backend Request Flow example.

**Files/Folders**

- `apps/backend/app/services/diagnosis_service.py`
- Update `apps/backend/app/api/routes/diagnostics.py`

**Implementation**
`diagnosis_service.run_diagnosis(connection_id)`: pulls recent evidence from the app DB (collected by Step 14's worker, computed by Step 15's engine), invokes `agents/graph_diagnosis.py` (Step 18), persists the resulting report to `diagnoses`/`evidence_graph_*` tables (Step 6 models), and returns it. Wire into `diagnostics.py` routes: `GET /connections/{id}/diagnoses`, `GET /diagnoses/{id}`.

**Dependencies**
Step 18 (agent graph), Step 6/7 (diagnosis models + migration), Step 10 (route stubs).

**Verification**
End-to-end API test: `POST /connections` → seed telemetry → `GET /connections/{id}/diagnoses` returns a persisted, evidence-traceable root-cause report.

**Expected Result**
Feature 1 (Root Cause Diagnosis) fully functional end-to-end through the API.

---

## Step 20 — Feature 2 Tools: HypoPG, Shadow DB, Policy Engine

**Goal**
Implement the simulation/verification toolset per `ARCHITECTURE.md` §4/§8 and `PRD.md` §5 Feature 2.

**Files/Folders**

- `apps/backend/app/tools/hypopg_tool.py`
- `apps/backend/app/tools/shadow_db_tool.py`
- `apps/backend/app/tools/policy_engine.py` (complete the Step 17 stub)
- `apps/backend/app/workers/shadow_lab_worker.py`

**Implementation**
- `hypopg_tool.py`: session-local hypothetical index creation/drop via the `hypopg` extension against the monitored DB; cost comparison helpers; clearly labels results as planner-cost signals only (per `PRD.md` §5).
- `shadow_db_tool.py`: clone monitored DB into an ephemeral Docker Postgres container via `pg_dump`/`pg_restore` (primary mode per `TECHSTACK.md`), install candidates, tear down after experiment.
- `shadow_lab_worker.py`: async worker provisioning/destroying shadow containers on demand for experiments.
- `policy_engine.py`: deterministic rule evaluator (`evaluate(verification_result) -> APPROVE/BLOCK`) implementing thresholds from `PRD.md` §5 Feature 2 (p95 improvement threshold, CI excludes zero, regression rate threshold, write-latency threshold, storage threshold, skeptic score threshold) — no LLM involvement, values configurable/TBD exact numeric thresholds per `PRD.md` §24.

**Dependencies**
Step 11 (customer_db pool for guarded write path), Step 17 (stub), `SHADOW_DB_IMAGE` config (Step 3).

**Verification**
Create a hypothetical index via `hypopg_tool` against a test DB and confirm planner cost changes; provision and tear down a shadow container end-to-end; run `policy_engine.evaluate()` against fixture verification results and confirm correct APPROVE/BLOCK output.

**Expected Result**
All Feature 2 low-level tools working independently and ready for agent orchestration.

---

## Step 21 — Feature 2 ML: Query Performance Delta Predictor

**Goal**
Implement the outcome-prediction model per `TECHSTACK.md`/`ARCHITECTURE.md` §4/§8.

**Files/Folders**

- `apps/backend/app/ml/delta_predictor/train.py`
- `apps/backend/app/ml/delta_predictor/predict.py`
- `apps/backend/app/ml/delta_predictor/features.py`

**Implementation**
LightGBM regression predicting Δlatency, Δp95, ΔCPU, ΔI/O, Δbuffer-reads with uncertainty, trained on self-generated experiment data (Database Optimization Laboratory, Step 21b) including deliberately bad candidates (GOOD/BAD/NEUTRAL/REGRESSION labels per `PRD.md` §7). MLflow-tracked, same pattern as Step 16.

**Dependencies**
Step 20 (shadow DB/HypoPG tools reused by the lab), Step 3 (MLflow config).

**Verification**
`train.py` runs on lab-generated fixture data; `predict.py` returns Δ-estimates + confidence interval on held-out samples.

**Expected Result**
A working delta-prediction model available to Feature 2's ML Scientist agent.

---

## Step 21b — Database Optimization Laboratory (Training Data Generator)

**Goal**
Build the experiment-generation pipeline for Step 21 and (reused) Step 23 models, per `PRD.md` §7.

**Files/Folders**

- `apps/backend/app/ml/delta_predictor/optimization_lab/` (new subpackage: `candidate_gen.py`, `experiment_runner.py`, `dataset_writer.py`)

**Implementation**
Uses TPC-H (primary, per `TECHSTACK.md`) benchmark databases; generates deterministic candidates (indexes, statistics changes), runs them through `hypopg_tool`/`shadow_db_tool` (Step 20), records baseline vs. candidate execution metrics into `optimization_experiments`-shaped records for training.

**Dependencies**
Step 20 (shadow/hypopg tools), Step 6 (`optimization_experiments` model for eventual reuse).

**Verification**
Run one full experiment generation cycle; confirm a valid labeled record matching `PRD.md` §5 Feature 2 example JSON structure.

**Expected Result**
Repeatable training-data generator for Feature 2/3 ML models.

---

## Step 22 — Feature 2 Agent Graph (Simulation & Verification)

**Goal**
Implement the LangGraph orchestration for simulation/verification/deployment, per `ARCHITECTURE.md` §8 and `PRD.md` §6.

**Files/Folders**

- `apps/backend/app/agents/graph_simulation.py`

**Implementation**
Wire the sequence: Experiment Agent (mechanical — calls `shadow_db_tool`/`hypopg_tool`) → ML Scientist Agent (interprets `delta_predictor/predict.py` output, requests more experiments if confidence low) → Skeptic Agent (adversarial, searches for regressions using `pg_introspection.py`) → Verification Agent (produces VERIFIED/CONDITIONAL/REJECTED using paired statistical tests — bootstrap CI, effect size, regression-rate check via scipy) → Policy Agent (calls `tools/policy_engine.py`, non-overridable) → Deployment Agent (executes approved canary changes — implemented fully in Step 23).

**Dependencies**
Step 20 (tools), Step 21 (ML model), Step 18 (`llm_client.py` reused).

**Verification**
Run `graph_simulation.py` against a fixture candidate; confirm each agent stage produces expected structured output and the Policy Agent correctly blocks a fixture candidate that fails thresholds.

**Expected Result**
Feature 2's full agentic pipeline functioning up to (not yet including) live canary execution.

---

## Step 23 — Canary Deployment, Rollback & Simulation Service (Feature 2 Complete)

**Goal**
Implement guarded production execution and wire Feature 2 into the API, per `ARCHITECTURE.md` §1/§4/§9, `PRD.md` §9.

**Files/Folders**

- `apps/backend/app/services/simulation_service.py`
- `apps/backend/app/workers/canary_monitor.py`
- Update `apps/backend/app/api/routes/experiments.py`
- Update Deployment Agent logic inside `apps/backend/app/agents/graph_simulation.py`

**Implementation**
- Deployment Agent: executes the approved, policy-passed action (`CREATE INDEX CONCURRENTLY`, `ANALYZE`) via `db/customer_db.py`'s guarded write path — only reachable after Policy Agent pass + human approval (Step 24).
- `canary_monitor.py`: background worker watching the live canary window (`CANARY_MONITOR_WINDOW_MINUTES`), tracking p50/p95/p99/error rate/lock waits/CPU/IO/throughput/write latency via `pg_introspection.py`, triggering automatic rollback (`DROP INDEX`, or revert config/query) on threshold breach.
- `simulation_service.py`: orchestrates `graph_simulation.py` invocation, persists experiment/prediction/verdict/deployment records, exposes functions for the `experiments.py` routes: `POST /recommendations/{id}/simulate`, `GET /recommendations/{id}/verification`, `GET /deployments/{id}`, `GET /experiments`.
- Add the SSE endpoint `GET /api/v1/experiments/{id}/canary/stream` (per `ARCHITECTURE.md` §1) pushing live canary metrics.

**Dependencies**
Step 22 (agent graph), Step 6/7 (experiment/deployment models), Step 11 (guarded write path).

**Verification**
End-to-end test: candidate → simulate → verify → (mock) approve → canary → threshold breach → automatic rollback recorded; SSE stream delivers live metric updates during the canary window.

**Expected Result**
Feature 2 (Safe Simulation & Verification Sandbox) fully functional end-to-end, including automatic rollback.

---

## Step 24 — Human Approval Gate (Safety Mechanism)

**Goal**
Enforce mandatory human approval before any production-modifying action, per `PRD.md` §6/§9/§22 and `ARCHITECTURE.md` §7.

**Files/Folders**

- `apps/backend/app/services/simulation_service.py` (extend)
- Update `apps/backend/app/api/routes/experiments.py` (`POST /recommendations/{id}/approve`, `POST /recommendations/{id}/reject`)
- `apps/backend/app/models/` — ensure `approvals` model (Step 6) is populated here

**Implementation**
`approve_recommendation()`: verifies the caller has an authorized role (RBAC scheme TBD, per `PRD.md` §24 — implement minimal role check against `User.role` for now), records an `approvals` row (who/when/what action), and only then unlocks the Deployment Agent path in Step 23. `reject_recommendation()` records rejection and halts the pipeline. No production-modifying action may execute without a preceding `approvals` record — enforce this as a hard check inside the Deployment Agent itself (defense in depth), not only at the route layer.

**Dependencies**
Step 23 (deployment path to gate), Step 8 (auth/RBAC primitives), Step 6 (approvals model).

**Verification**
Attempt to trigger canary deployment without a prior approval record → rejected; with approval → proceeds; unauthorized role attempting to approve → 403.

**Expected Result**
No production-modifying action can execute without a recorded, authorized human approval — satisfying `PRD.md` §22 acceptance criteria.

---

## Step 25 — Feature 3 ML Layer (L1 Forecasting, L2 Outcome, L3 Bandit, L4 Calibration)

**Goal**
Implement the predictive/closed-loop ML stack per `TECHSTACK.md`/`ARCHITECTURE.md` §4/§8 and `PRD.md` §5 Feature 3.

**Files/Folders**

- `apps/backend/app/ml/forecasting/train.py`
- `apps/backend/app/ml/forecasting/predict.py`
- `apps/backend/app/ml/forecasting/features.py`
- `apps/backend/app/ml/bandit/policy.py`

**Implementation**
- `forecasting/`: L1 — LightGBM regression with lag/rolling-window features (1h–168h), growth rates, calendar features, conformal prediction for calibrated intervals; outputs `degradation_probability(t)`. Walk-forward temporal train/test split only (no random split).
- `bandit/policy.py`: L3 — Contextual Thompson Sampling over actions `{index, partial_index, rewrite, statistics, vacuum, config, do_nothing}`; reward = performance/IO/CPU improvement − risk penalty − implementation cost; implements the mandatory rollout gate (rule-based → supervised → bandit → offline-evaluated via Inverse Propensity Scoring) before bandit output may influence live recommendations, per `PRD.md` §5/§22.
- L2 (Optimization Outcome Model) reuses `ml/delta_predictor/` from Step 21 (per `TECHSTACK.md`: "same model family... one LightGBM training pipeline reused").
- L4 (Learning & Calibration): implement as part of `retrain_worker.py` in Step 26 — MAE/RMSE/coverage tracking, calibration report, drift detection (Evidently) — not a standalone ML file but a workflow (see Step 26).

**Dependencies**
Step 14 (telemetry history), Step 21b (experiment records as training data), Step 3 (MLflow config).

**Verification**
`forecasting/train.py` produces a model with walk-forward validation metrics logged to MLflow; `bandit/policy.py` unit test confirms Thompson Sampling selects higher-historical-reward actions more often over repeated trials; confirm bandit output is gated off by default (rollout phase flag).

**Expected Result**
Working forecasting and strategy-selection models, correctly rollout-gated per safety requirements.

---

## Step 26 — Retrain Worker & Closed-Loop Learning (L4)

**Goal**
Implement the feedback loop and model promotion workflow, per `ARCHITECTURE.md` §4 (`retrain_worker.py`) and `PRD.md` §5 Feature 3 L4/§7.

**Files/Folders**

- `apps/backend/app/workers/retrain_worker.py`

**Implementation**
Scheduled worker: reads new labeled `optimization_experiments` records (from Feature 2 outcomes), computes prediction error (MAE/RMSE) per model version, updates calibration tracking (predicted-confidence vs. actual-coverage across ≥5 buckets per `PRD.md` §21), runs drift detection (Evidently, per `evidently.config.yaml`), retrains L1/L2/RCA-classifier models when volume/drift/schedule triggers fire, evaluates new versions against the currently-promoted version in MLflow, and promotes only if measurably better (per `PRD.md` §22 acceptance criteria).

**Dependencies**
Step 25 (models to retrain), Step 21b/16b (labeled experiment sources), Step 3 (`evidently.config.yaml` referenced via `infra/monitoring/`).

**Verification**
Run the worker against a fixture batch of new experiment outcomes; confirm MAE trend, calibration report, and correct promote/no-promote decision logged to MLflow.

**Expected Result**
A working, measurable "system improves over time" closed loop.

---

## Step 27 — Feature 3 Agent Graph & Service (Forecast/Planning + Learning)

**Goal**
Implement Feature 3's minimal agent layer and wire it into the API, per `ARCHITECTURE.md` §4/§8.

**Files/Folders**

- `apps/backend/app/agents/graph_forecast.py`
- `apps/backend/app/services/forecast_service.py`
- Update `apps/backend/app/api/routes/forecasts.py`

**Implementation**
- `graph_forecast.py`: Forecasting/Planning Agent (reads L1 forecast + L3 bandit ranking, decides if degradation risk crosses threshold, requests a Feature 2 simulation via `simulation_service.py` from Step 23, compares predicted vs. simulated result) and Learning Agent (delegates to `retrain_worker.py` triggers, per Step 26 — thin wrapper, not duplicate logic).
- `forecast_service.py`: orchestrates forecast generation, persists to `forecasts`/`bandit_events` tables, exposes `GET /forecast/{connectionId}` and `GET /models/performance` (MAE-over-time, calibration report) route logic. Add the SSE endpoint `GET /api/v1/forecasts/{id}/stream` per `ARCHITECTURE.md` §1.

**Dependencies**
Step 25 (ML models), Step 26 (retrain worker), Step 23 (simulation_service to call into).

**Verification**
End-to-end test: seeded telemetry → forecast generated → risk above threshold → simulation request dispatched to Feature 2 → predicted-vs-actual comparison stored.

**Expected Result**
Feature 3 (Predictive ML + Closed-Loop Optimization) functional end-to-end through the API.

---

## Step 28 — Feature 4: ROI Service (Deterministic, No ML/LLM)

**Goal**
Implement the cost-to-dollar translation, per `PRD.md` §5 Feature 4 (marked largely TBD).

**Files/Folders**

- `apps/backend/app/services/roi_service.py`
- Update `apps/backend/app/api/routes/roi.py`

**Implementation**
Pure deterministic calculation service reading measured (post-canary, never predicted) deltas from `optimization_experiments`/`deployments` and mapping them to a dollar figure via a static pricing reference table (TBD — exact provider/pricing inputs not specified per `PRD.md` §5/§24; implement as a configurable lookup table with a clear "cost model not configured" fallback per `PRD.md` §5 Failure cases). No model or LLM involvement.

**Dependencies**
Step 23 (measured deployment deltas), Step 6/7 (`roi_records` model).

**Verification**
Given fixture measured deltas, `roi_service` produces a deterministic dollar estimate matching manual calculation; missing pricing config returns the "not configured" state, never a fabricated number.

**Expected Result**
Feature 4 functional to the extent the source documents specify, with all TBD gaps clearly surfaced rather than guessed.

---

## Step 29 — Background Worker Process Wiring

**Goal**
Ensure all workers run as independent processes/containers, per `ARCHITECTURE.md` §4/§6.

**Files/Folders**

- `apps/backend/app/workers/telemetry_collector.py` (entrypoint hardening)
- `apps/backend/app/workers/retrain_worker.py` (entrypoint hardening)
- `apps/backend/app/workers/canary_monitor.py` (entrypoint hardening)
- `apps/backend/app/workers/shadow_lab_worker.py` (entrypoint hardening)

**Implementation**
Add a `if __name__ == "__main__":` (or CLI arg-driven) entrypoint to each worker so a single `worker.Dockerfile` image can run any of the four via a different command/entrypoint argument (per `ARCHITECTURE.md` §6 — "avoiding four near-duplicate images"). Confirm each worker communicates with the API only indirectly through the application database (no message queue, per `ARCHITECTURE.md` §10 — queue explicitly not introduced unless volume requires it, TBD).

**Dependencies**
Steps 14, 20, 23, 26 (worker logic already implemented).

**Verification**
Run each worker standalone via its entrypoint argument; confirm no dependency on the FastAPI process.

**Expected Result**
All four background workers independently runnable and container-ready.

---

## Step 30 — Caching / Queue Evaluation (Explicitly TBD)

**Goal**
Confirm whether Redis/message queues are required, per `ARCHITECTURE.md` §10 and `PRD.md` §16/§24.

**Files/Folders**

None created by default.

**Implementation**
Per source documents, no queue is mandated: workers communicate via the application database only. TBD: revisit only if implementation-time background job volume necessitates it (per `PRD.md` §10/§16/§24). Do not add Redis/RabbitMQ/Celery unless a concrete bottleneck is measured.

**Dependencies**
Step 29.

**Verification**
N/A — document the decision (no queue) in code comments/README if this step is skipped.

**Expected Result**
Explicit, documented non-decision preventing unnecessary infrastructure additions.

---

## Step 31 — Audit Logging & Observability Wiring

**Goal**
Implement full observability per `ARCHITECTURE.md` §4 (`core/logging.py` usage) and `PRD.md` §15.

**Files/Folders**

- `apps/backend/app/services/` (add audit-write calls into `simulation_service.py`, `diagnosis_service.py`, `roi_service.py`)
- `apps/backend/app/core/logging.py` (extend with request/agent/experiment correlation IDs)

**Implementation**
Ensure every production-modifying action (DDL execution, config change, canary commit/rollback) writes an `audit_log` row (actor, action, timestamp, policy verdict, outcome) per `PRD.md` §14/§22. Add structured agent execution logging (per-agent tool calls, evidence produced, confidence) feeding both the evidence-graph UI and debugging, per `PRD.md` §15. Log collector uptime/failures, canary rollback events, and model drift as flagged alert conditions (exact alerting channel TBD per `PRD.md` §15/§24).

**Dependencies**
Step 23/24 (deployment + approval flow), Step 6 (`audit_log` model), Step 4 (logging base).

**Verification**
Trigger a full diagnosis → simulate → approve → canary → rollback cycle; confirm a complete, retrievable audit trail exists for every step.

**Expected Result**
Every production-modifying action is fully auditable, satisfying `PRD.md` §22.

---

## Step 32 — Global Error Handling

**Goal**
Standardize API error responses and failure handling across all routes/services.

**Files/Folders**

- `apps/backend/app/api/deps.py` (exception dependency, if applicable)
- `apps/backend/app/main.py` (exception handlers)
- `apps/backend/app/core/config.py` (no change — reference only)

**Implementation**
FastAPI exception handlers for: validation errors (422), auth failures (401/403), not-found (404), and domain-specific failures per PRD "Failure cases" sections — insufficient telemetry (cold start), shadow DB provisioning failure (falls back to labeled lower-confidence estimate, never silently upgraded), underpowered statistical test (verdict downgraded to CONDITIONAL), missing ROI pricing config (marked "not configured"). Each handler returns a consistent JSON error schema (exact schema TBD per `PRD.md` §12/§24).

**Dependencies**
Step 10 (routes), Steps 12–28 (services whose failure modes are handled here).

**Verification**
Trigger each documented failure case (e.g., disconnect shadow DB mid-provision) and confirm the API returns the documented degraded-but-honest response rather than a crash or silent success.

**Expected Result**
All documented PRD failure cases are handled gracefully and consistently.

---

## Step 33 — Unit Tests

**Goal**
Cover deterministic and isolated logic with unit tests, per `ARCHITECTURE.md` §4 (`tests/`).

**Files/Folders**

- `apps/backend/tests/unit/test_evidence_engine.py`
- `apps/backend/tests/unit/test_policy_engine.py`
- `apps/backend/tests/unit/test_security.py`
- `apps/backend/tests/unit/test_pg_introspection.py`
- `apps/backend/tests/unit/test_ml_predict.py` (per model)
- `apps/backend/tests/unit/test_roi_service.py`

**Implementation**
Unit tests (pytest) for: evidence engine calculations (Step 15), policy engine rule evaluation (Step 20), security/encryption primitives (Step 8), introspection tool parsing against fixture DB rows (Step 13), each ML `predict.py`'s output shape/bounds (Steps 16, 21, 25), ROI deterministic math (Step 28).

**Dependencies**
All corresponding implementation steps above.

**Verification**
`pytest apps/backend/tests/unit -v` passes with meaningful coverage of deterministic/pure-function logic.

**Expected Result**
Core deterministic logic is regression-tested.

---

## Step 34 — API Integration Tests

**Goal**
Test full request→response flows across the API, per `ARCHITECTURE.md` §4/§10.

**Files/Folders**

- `apps/backend/tests/integration/test_auth_flow.py`
- `apps/backend/tests/integration/test_connections_flow.py`
- `apps/backend/tests/integration/test_diagnosis_flow.py`
- `apps/backend/tests/integration/test_simulation_flow.py`
- `apps/backend/tests/integration/test_forecast_flow.py`
- `apps/backend/tests/integration/test_roi_flow.py`
- `apps/backend/tests/integration/test_approval_gate.py`

**Implementation**
Using `httpx.AsyncClient`/FastAPI `TestClient` against a test application DB and test monitored Postgres instance: signup/login → connect DB → collect telemetry → run diagnosis → generate recommendation → simulate → verify → approve → canary → rollback/commit → check audit log → check ROI. Include a negative test confirming no canary executes without a prior approval record (Step 24).

**Dependencies**
Steps 1–32 (full backend implemented).

**Verification**
`pytest apps/backend/tests/integration -v` passes against a fully seeded test environment (test app DB + test monitored Postgres, both via Docker Compose test profile).

**Expected Result**
Every documented user journey in `PRD.md` §4 is verified working end-to-end.

---

## Step 35 — Security Review & Hardening Checks

**Goal**
Verify all security requirements from `ARCHITECTURE.md` §14 / `PRD.md` §14 are actually enforced.

**Files/Folders**

No new files; review across `core/security.py`, `db/customer_db.py`, `api/deps.py`, `tools/policy_engine.py`.

**Implementation**
Checklist review: connection strings encrypted at rest (verify DB column contents are ciphertext, not plaintext); credentials never appear in logs (grep log output during a full test run); application DB never reachable from frontend directly; monitored-DB role documented as least-privilege read-only, with the separately-scoped canary write path invoked only by the Deployment Agent post-approval; no LLM-generated raw SQL ever reaches `customer_db.py`'s execute path (confirm only policy_engine-approved, deterministically-generated statements are executed); tenant isolation mechanism status recorded as TBD (per `PRD.md` §14/§24) with a note for future resolution before multi-tenant launch; sensitive query-text redaction approach recorded as TBD (per `PRD.md` §24).

**Dependencies**
Steps 8, 11, 20, 23, 24.

**Verification**
Manual/automated review checklist completed with each item marked pass or explicitly TBD (not silently skipped).

**Expected Result**
All specified security requirements are verifiably enforced or explicitly flagged as open (TBD) per source docs.

---

## Step 36 — Dockerization

**Goal**
Containerize all backend services per `ARCHITECTURE.md` §6.

**Files/Folders**

- `apps/backend/Dockerfile`
- `infra/docker/backend.Dockerfile`
- `infra/docker/worker.Dockerfile`
- `infra/docker/shadow-db.Dockerfile`
- `infra/monitoring/mlflow.env`
- `infra/monitoring/evidently.config.yaml`
- `docker-compose.yml` (root)

**Implementation**
- `backend.Dockerfile`: builds the FastAPI app image, runs `uvicorn app.main:app`.
- `worker.Dockerfile`: shared image for all four workers (Step 29), worker selected via entrypoint/command arg.
- `shadow-db.Dockerfile`: plain Postgres image pre-installed with `pg_stat_statements` and `hypopg` extensions.
- `mlflow.env`: MLflow tracking server config (backing store = application Postgres, artifact store = local volume).
- `evidently.config.yaml`: drift-check configuration consumed by `retrain_worker.py` (Step 26).
- `docker-compose.yml`: service definitions for application DB, backend API, all four workers (via `worker.Dockerfile` + different commands), MLflow container, shadow-DB template — network per `ARCHITECTURE.md` §6 (single Compose network; only frontend+backend publish ports; app DB/MLflow/shadow DBs internal-only), secrets via root `.env`.

**Dependencies**
Steps 1–35 (complete backend to containerize).

**Verification**
`docker-compose up` brings up application DB, backend API, all workers, and MLflow successfully; `GET /docs` reachable on the published backend port; internal-only services unreachable from host.

**Expected Result**
The full backend stack runs reproducibly via a single `docker-compose up` command.

---

## Step 37 — Final Backend Verification

**Goal**
Confirm the complete backend satisfies every acceptance criterion in `PRD.md` §22.

**Files/Folders**

No new files; full-system verification pass.

**Implementation**
Run the full Step 34 integration suite plus Step 35 security checklist against the Dockerized stack (Step 36). Confirm each `PRD.md` §22 acceptance criterion individually: evidence-traceable diagnoses; no "verified" optimization skips HypoPG → ML → shadow → statistics → Skeptic → Policy order; no production action without approval record; automatic rollback on threshold breach without human input; every experiment produces a retrievable predicted-vs-actual record; model promotion only on measurable improvement (MLflow); bandit-influenced recommendations withheld until offline policy evaluation complete; every production-modifying action has a complete audit log entry.

**Dependencies**
All previous steps.

**Verification**
Checklist walkthrough with the running Dockerized stack; all items pass or are explicitly marked TBD with a documented reason.

**Expected Result**
A complete, verified backend implementation of the AI Database Administrator, ready for frontend integration and further iteration on TBD items.

---

## Backend Build Order

1. Project scaffolding
2. Dependencies & packaging
3. Environment variables & settings
4. Structured logging
5. Application DB connection layer
6. Application DB models
7. Alembic migrations
8. Authentication & authorization core
9. Pydantic schemas
10. Core API skeleton
11. Customer DB connection manager
12. Connection onboarding service
13. PostgreSQL introspection tools
14. Telemetry collector worker
15. Deterministic evidence engine
16. Feature 1 ML models (anomaly, temporal, RCA classifier) + 16b Fault Laboratory
17. Agent tooling boundary review / policy engine stub
18. LLM client + Feature 1 agent graph
19. Diagnosis service & API (Feature 1 complete)
20. Feature 2 tools (HypoPG, shadow DB, policy engine)
21. Feature 2 ML (delta predictor) + 21b Optimization Laboratory
22. Feature 2 agent graph
23. Canary deployment, rollback, simulation service (Feature 2 complete)
24. Human approval gate
25. Feature 3 ML (forecasting, bandit)
26. Retrain worker & closed-loop learning
27. Feature 3 agent graph & service (Feature 3 complete)
28. Feature 4 ROI service
29. Background worker process wiring
30. Caching/queue evaluation (TBD, likely skipped)
31. Audit logging & observability
32. Global error handling
33. Unit tests
34. API integration tests
35. Security review & hardening
36. Dockerization
37. Final backend verification

---

## Backend Definition of Done

### APIs

- [ ] All endpoints from `PRD.md` §12 implemented and documented via OpenAPI (`/docs`)
- [ ] SSE endpoints for canary and forecast streams working
- [ ] Consistent error schema across all routes

### Database

- [ ] Application DB schema matches `PRD.md` §13 (all core + inferred entities)
- [ ] Alembic migrations reproducible (`upgrade head` / `downgrade base`)
- [ ] Customer DB access exclusively through `tools/` (no ORM models for monitored DB)

### Authentication

- [ ] JWT httpOnly cookie login/session working
- [ ] `get_current_user` enforced on all protected routes
- [ ] RBAC for approval actions implemented (exact scheme TBD, minimal role check present)

### Agents

- [ ] Feature 1 graph (5 specialists + Supervisor) producing evidence-traceable root-cause reports
- [ ] Feature 2 graph (Experiment → ML Scientist → Skeptic → Verification → Policy → Deployment) enforced in strict order
- [ ] Feature 3 graph (Forecast/Planning + Learning) requesting simulation only via Feature 2
- [ ] No agent has unrestricted SQL or raw credentials

### AI/ML

- [ ] Anomaly detector, temporal model, RCA classifier trained and served (Feature 1)
- [ ] Delta predictor trained and served (Feature 2, reused as L2 in Feature 3)
- [ ] L1 forecasting model with conformal intervals; L3 bandit with rollout gating; L4 calibration/drift tracking (Feature 3)
- [ ] All models tracked/versioned in MLflow with walk-forward validation

### Tools

- [ ] `pg_introspection.py` fully read-only and covers all telemetry sources in `PRD.md` §8
- [ ] `hypopg_tool.py`, `shadow_db_tool.py` functioning independently
- [ ] `policy_engine.py` deterministic, non-LLM-overridable

### Tests

- [ ] Unit tests cover deterministic engine, policy engine, security, ML predict shapes, ROI math
- [ ] Integration tests cover full user journey (§4) including approval-gate negative test
- [ ] All tests passing in CI-equivalent local run

### Security

- [ ] Connection strings encrypted at rest, verified via DB inspection
- [ ] No credentials in logs
- [ ] No LLM-generated SQL reaches production execution path
- [ ] Tenant isolation and query-text redaction explicitly documented as TBD if unresolved

### Observability

- [ ] Structured logging across all layers
- [ ] Full audit trail for every production-modifying action
- [ ] Agent execution logs available per investigation

### Deployment

- [ ] `docker-compose up` runs full backend stack (API, 4 workers, app DB, MLflow, shadow DB template)
- [ ] Only frontend/backend ports published; app DB/MLflow/shadow DBs internal-only
- [ ] All secrets sourced from `.env`, none hardcoded or committed
