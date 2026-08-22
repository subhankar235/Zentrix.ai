<div align="center">

# Zentrix.ai Backend

**Autonomous Agentic Database Tuning & Performance Verification Engine**

An AI-native backend for continuously observing PostgreSQL databases, investigating root causes of performance issues, safely verifying optimization strategies, predicting future degradation, and learning from outcomes.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.8-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0.38-778899.svg)](https://www.sqlalchemy.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.70-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Folder Structure](#folder-structure)
- [Request Lifecycle](#request-lifecycle)
- [API Endpoints](#api-endpoints)
- [Agent Modules](#agent-modules)
- [ML Pipeline](#ml-pipeline)
- [Database Schema](#database-schema)
- [Authentication & Security](#authentication--security)
- [Configuration](#configuration)
- [Environment Variables](#environment-variables)
- [Installation](#installation)
- [Development](#development)
- [Running the Server](#running-the-server)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [Docker](#docker)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Zentrix.ai is an autonomous database intelligence platform that goes beyond traditional monitoring. Instead of telling you a query is slow, it determines **why** it is slow, what optimization should be applied, tests it in a safe shadow environment, verifies the improvement statistically, and learns from the outcome to improve future recommendations.

### Design Philosophy

```
Deterministic evidence pipeline first, ML second, LLM/agents last.
```

The LLM never invents facts or executes SQL directly. It reasons over structured evidence produced by collectors, statistical engines, and trained models.

### How It Works

1. **Connect** your PostgreSQL database (Neon, RDS, Supabase, or self-hosted)
2. **Telemetry Collector** polls `pg_stat_statements`, `pg_stat_activity`, and other system views
3. **Deterministic Evidence Engine** computes hard metrics — cardinality error, plan diffs, lock chains, vacuum lag
4. **ML Layer** scores anomalies on a multivariate feature vector (Isolation Forest + LightGBM)
5. **Specialized Agents** (LangGraph) investigate one domain each and emit hypotheses
6. **Supervisor Agent** reconciles contradictions, produces ranked root-cause report
7. **Simulation Sandbox** tests optimizations on shadow databases with production workload replay
8. **Statistical Verification** validates results before any production change
9. **Closed-Loop Learning** feeds outcomes back into training models

---

## Architecture Overview

```mermaid
graph TD
    subgraph "Frontend"
        FE["Next.js Dashboard"]
    end

    subgraph "Backend (FastAPI)"
        API["REST API + SSE Streams"]
        AUTH["JWT Auth + RBAC"]
        ROUTER["API Router"]
        SERVICES["Business Logic Services"]
    end

    subgraph "Agent Layer (LangGraph)"
        DIAG_GRAPH["Diagnosis Graph"]
        SIM_GRAPH["Simulation Graph"]
        FORECAST_GRAPH["Forecast Graph"]
        SUPERVISOR["Supervisor Agent"]
    end

    subgraph "ML Pipeline"
        ANOMALY["Isolation Forest<br/>Anomaly Detection"]
        CLASSIFIER["LightGBM<br/>Root Cause Classifier"]
        FORECASTER["LightGBM<br/>Degradation Forecasting"]
        BANDIT["Thompson Sampling<br/>Strategy Selector"]
        DRIFT["Evidently<br/>Drift Detection"]
    end

    subgraph "Tools"
        PG_INTROSPECT["PG Introspection"]
        POLICY["Policy Engine"]
        HYPOPG["HypoPG Simulation"]
        SHADOW["Shadow DB Manager"]
    end

    subgraph "Data Layer"
        APP_DB[("App DB<br/>PostgreSQL")]
        CUST_DB[("Customer DB<br/>PostgreSQL")]
        MLFLOW["MLflow<br/>Model Registry"]
        DUCKDB["DuckDB<br/>Analytics"]
    end

    subgraph "Workers"
        TELEMETRY["Telemetry Collector"]
        SHADOW_LAB["Shadow Lab Worker"]
        RETRAIN["Retrain Worker"]
        CANARY["Canary Monitor"]
    end

    FE --> API
    API --> AUTH
    API --> ROUTER
    ROUTER --> SERVICES
    SERVICES --> DIAG_GRAPH
    SERVICES --> SIM_GRAPH
    SERVICES --> FORECAST_GRAPH
    DIAG_GRAPH --> SUPERVISOR
    SIM_GRAPH --> SUPERVISOR
    FORECAST_GRAPH --> SUPERVISOR
    DIAG_GRAPH --> ANOMALY
    DIAG_GRAPH --> CLASSIFIER
    FORECAST_GRAPH --> FORECASTER
    SIM_GRAPH --> BANDIT
    DIAG_GRAPH --> PG_INTROSPECT
    SIM_GRAPH --> POLICY
    SIM_GRAPH --> HYPOPG
    SIM_GRAPH --> SHADOW
    SERVICES --> APP_DB
    TOOLS --> CUST_DB
    ML --> MLFLOW
    TOOLS --> DUCKDB
    TELEMETRY --> CUST_DB
    SHADOW_LAB --> SHADOW
    RETRAIN --> MLFLOW
    CANARY --> CUST_DB
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent Root Cause Investigation** | 6 specialized LangGraph agents investigate plan regressions, I/O pressure, lock contention, vacuum lag, schema issues, and reconcile evidence into a ranked diagnosis |
| **Evidence Graph** | Directed graph of metrics, anomalies, hypotheses, and root causes — fully auditable |
| **Safe Simulation Sandbox** | Shadow DB cloning via `pg_dump`/`pg_restore` for risk-free optimization testing |
| **Statistical Verification** | Hypothesis testing with p-values, confidence intervals, and skeptic agent challenges |
| **Predictive Degradation Forecasting** | LightGBM-based 7-day degradation probability curves with conformal prediction intervals |
| **Closed-Loop Learning** | Experiment outcomes feed back into ML models; Thompson Sampling learns optimal strategies |
| **Canary Deployment with Auto-Rollback** | Production changes applied with observation windows and automatic rollback on regression |
| **ROI Translation** | Deterministic dollar-savings calculation from verified performance deltas |
| **Multi-Database Support** | Neon, RDS, Supabase, self-hosted — any PostgreSQL with `pg_stat_statements` |
| **Real-Time SSE Streams** | Live canary metrics and forecast computation streamed to the dashboard |
| **Human Approval Gates** | No production change without explicit DBA approval |
| **Audit Trail** | Immutable log of every authentication, database-modifying, and deployment event |

---

## Technology Stack

### Core

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12 |
| Web Framework | FastAPI | 0.115.8 |
| ASGI Server | Uvicorn | 0.34.0 |
| SSE Streaming | sse-starlette | 2.2.1 |
| Validation | Pydantic | 2.10.6 |
| Settings | pydantic-settings | 2.8.0 |

### Database

| Layer | Technology | Version |
|-------|-----------|---------|
| ORM | SQLAlchemy (async) | 2.0.38 |
| Async Driver | asyncpg | 0.30.0 |
| Migrations | Alembic | 1.14.1 |
| Target Database | PostgreSQL | 16+ |

### Authentication & Security

| Layer | Technology | Version |
|-------|-----------|---------|
| JWT Tokens | PyJWT | 2.10.1 |
| Password Hashing | bcrypt | 4.2.1 |
| Credential Encryption | Fernet (cryptography) | 44.0.1 |

### Agent Orchestration

| Layer | Technology | Version |
|-------|-----------|---------|
| Agent Framework | LangGraph | 0.2.70 |
| Core Orchestration | langchain-core | 0.3.36 |

### Machine Learning

| Layer | Technology | Version |
|-------|-----------|---------|
| Tabular ML | LightGBM | 4.5.0 |
| Anomaly Detection | scikit-learn | 1.6.1 |
| Deep Learning | PyTorch | 2.6.0 |
| Change Detection | ruptures | 1.1.9 |
| Experiment Tracking | MLflow | 2.20.2 |
| Drift Monitoring | Evidently | 0.4.38 |

### Data Processing

| Layer | Technology | Version |
|-------|-----------|---------|
| Numerical | NumPy | 1.26.4 |
| DataFrames | pandas | 2.2.3 |
| Lazy DataFrames | Polars | 1.22.0 |
| Statistics | SciPy | 1.14.1 |
| Analytical DB | DuckDB | 1.2.0 |

### Testing

| Layer | Technology | Version |
|-------|-----------|---------|
| Test Framework | pytest | 8.3.4 |
| Async Tests | pytest-asyncio | 0.25.3 |
| HTTP Client | httpx | 0.28.1 |

---

## Folder Structure

```
apps/backend/
│
├── alembic.ini                          # Alembic migration configuration
├── Dockerfile                           # Python 3.12-slim base image
├── requirements.txt                     # 54 pip dependencies
│
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app, lifespan, CORS, health checks
│   │
│   ├── core/                            # Cross-cutting concerns
│   │   ├── config.py                    # Pydantic Settings — env loading, DB URL normalization
│   │   ├── security.py                  # bcrypt hashing, JWT create/decode, Fernet AES encryption
│   │   └── logging.py                   # Structured JSON (prod) + human-readable (dev) formatters
│   │
│   ├── db/                              # Database access layer
│   │   ├── base.py                      # SQLAlchemy DeclarativeBase + TimestampMixin
│   │   ├── session.py                   # Async engine, session factory, health check
│   │   └── customer_db.py               # Singleton asyncpg pool manager for customer PG databases
│   │
│   ├── models/                          # SQLAlchemy ORM models (18 tables)
│   │   ├── user.py                      # User accounts (UUID PK, email, hashed pw, role)
│   │   ├── connection.py                # Monitored PG connections (encrypted credentials)
│   │   ├── telemetry.py                 # QueryMetric, TableMetric, PlanMetric
│   │   ├── diagnosis.py                 # Diagnosis + EvidenceGraphNode + EvidenceGraphEdge
│   │   ├── experiment.py                # OptimizationExperiment, ModelPrediction, BanditEvent
│   │   ├── forecast.py                  # ForecastRecord, ModelDriftReport
│   │   ├── roi.py                       # RoiRecord (dollar savings calculations)
│   │   ├── approval.py                  # Human approval/rejection records
│   │   └── audit.py                     # AuditLog + CanaryRun (immutable audit trail)
│   │
│   ├── schemas/                         # Pydantic v2 request/response schemas (9 files)
│   │   ├── user.py                      # UserCreate, UserLogin, TokenResponse
│   │   ├── connection.py                # ConnectionCreate, ConnectionTestResponse
│   │   ├── diagnosis.py                 # EvidenceGraph schemas, DiagnosisDetailOut
│   │   ├── experiment.py                # ExperimentVerificationOut, SimulationTriggerRequest
│   │   ├── forecast.py                  # DegradationCurvePoint, ForecastResponse
│   │   ├── telemetry.py                 # TelemetrySummaryResponse
│   │   ├── roi.py                       # RoiSummaryResponse
│   │   └── audit.py                     # AuditLog schemas
│   │
│   ├── api/                             # FastAPI route layer
│   │   ├── router.py                    # Central router aggregating all 6 sub-routers
│   │   ├── deps.py                      # Dependencies: auth, DB session, connection pool
│   │   └── routes/
│   │       ├── auth.py                  # POST signup/login/logout, GET /me
│   │       ├── connections.py           # CRUD connections, test, telemetry, diagnoses list
│   │       ├── diagnostics.py           # GET diagnosis report, trigger investigation
│   │       ├── experiments.py           # CRUD experiments, simulate, verify, approve, SSE canary
│   │       ├── forecasts.py             # GET forecast, model performance, SSE forecast stream
│   │       └── roi.py                   # GET ROI summary per connection, per experiment
│   │
│   ├── services/                        # Business logic layer
│   │   ├── connection_service.py        # Connection lifecycle management
│   │   ├── diagnosis_service.py         # Diagnosis orchestration
│   │   ├── evidence_engine.py           # Deterministic evidence computation
│   │   ├── simulation_service.py        # Shadow DB simulation coordination
│   │   ├── forecast_service.py          # Forecast generation and model evaluation
│   │   └── roi_service.py               # Dollar-savings calculation engine
│   │
│   ├── agents/                          # LangGraph multi-agent orchestration
│   │   ├── llm_client.py               # LLM client wrapper
│   │   ├── graph_diagnosis.py           # Diagnosis LangGraph state machine
│   │   ├── graph_simulation.py          # Simulation LangGraph state machine
│   │   ├── graph_forecast.py            # Forecast LangGraph state machine
│   │   ├── diagnosis/                   # Feature 1: Root Cause Investigation
│   │   │   ├── planner_agent.py         # Query plan / statistics investigator
│   │   │   ├── io_buffer_agent.py       # I/O and buffer cache investigator
│   │   │   ├── concurrency_agent.py     # Lock / contention investigator
│   │   │   ├── vacuum_agent.py          # Vacuum / autovacuum investigator
│   │   │   ├── schema_index_agent.py    # Schema / index investigator
│   │   │   └── supervisor_agent.py      # Reconciles all agent evidence
│   │   ├── simulation/                  # Feature 2: Safe Simulation
│   │   │   ├── experiment_agent.py      # Orchestrates simulation experiment
│   │   │   ├── skeptic_agent.py         # Challenges verification results
│   │   │   ├── ml_scientist_agent.py    # Statistical significance testing
│   │   │   ├── policy_agent.py          # Risk/policy gate enforcement
│   │   │   ├── verification_agent.py    # Before/after comparison
│   │   │   └── deployment_agent.py      # Canary deployment orchestration
│   │   └── forecast/                    # Feature 3: Predictive ML
│   │       ├── forecasting_planning_agent.py  # Forecast computation
│   │       └── learning_agent.py              # Closed-loop model updates
│   │
│   ├── tools/                           # Deterministic database tools
│   │   ├── pg_introspection.py          # PostgreSQL system view queries
│   │   ├── policy_engine.py             # SQL safety / risk classifier
│   │   ├── hypopg_tool.py              # HypoPG index simulation
│   │   └── shadow_db_tool.py           # Shadow DB clone tool
│   │
│   ├── ml/                              # Machine Learning modules
│   │   ├── temporal/                    # Time-series forecasting
│   │   │   ├── features.py             # Feature engineering for time-series
│   │   │   ├── train.py                # ARIMA/LSTM model training
│   │   │   └── predict.py              # Degradation probability prediction
│   │   ├── rca_classifier/             # Root cause classification
│   │   │   ├── features.py             # Feature extraction for RCA
│   │   │   ├── train.py                # LightGBM/XGBoost classifier training
│   │   │   └── predict.py              # Root cause prediction
│   │   └── bandit/                     # Contextual bandit for strategy selection
│   │       └── policy.py               # Thompson Sampling policy
│   │
│   └── workers/                         # Background async workers
│       ├── telemetry_collector.py       # Polls PG system views periodically
│       ├── shadow_lab_worker.py         # Manages shadow DB containers
│       ├── retrain_worker.py            # Scheduled ML model retraining
│       └── canary_monitor.py            # Observes canary deployments
│
├── migrations/                          # Alembic database migrations
│   ├── env.py                           # Async Alembic env
│   └── versions/                        # Migration version files
│
└── tests/                               # Test suite
    ├── unit/                            # 11 unit test files
    └── integration/                     # 9 integration test files
```

---

## Request Lifecycle

```mermaid
sequenceDiagram
    participant Client as Frontend / Client
    participant FastAPI as FastAPI Router
    participant Auth as Auth Middleware
    participant Deps as Dependency Injection
    participant Route as Route Handler
    participant Service as Business Logic
    participant Agent as LangGraph Agent
    participant DB as Application DB
    participant CustDB as Customer DB

    Client->>FastAPI: HTTP Request
    FastAPI->>Auth: Extract JWT (cookie/header)
    Auth->>Auth: Decode & validate token
    Auth->>Deps: Resolve User entity
    Deps->>DB: SELECT user by UUID
    DB-->>Deps: User record
    Deps->>Route: Inject authenticated User
    Route->>Service: Execute business logic
    Service->>Agent: Trigger agent workflow (if needed)
    Agent->>CustDB: Query PG system views
    CustDB-->>Agent: Telemetry evidence
    Agent->>Agent: Process, reason, produce diagnosis
    Agent-->>Service: Structured results
    Service->>DB: Persist results
    Service-->>Route: Response data
    Route-->>Client: JSON Response / SSE Stream
```

### Stages

1. **Token Extraction** — JWT extracted from httpOnly secure cookie (priority) or `Authorization: Bearer` header
2. **Token Validation** — HS256 signature verified, expiration checked
3. **User Resolution** — UUID lookup or email fallback against the `users` table
4. **Ownership Verification** — Connection resources validated against user ownership
5. **Business Logic** — Services coordinate agents, tools, and database operations
6. **Response** — JSON serialization or SSE event stream

---

## API Endpoints

All endpoints are prefixed with `/api/v1`.

### Authentication — `/auth`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/signup` | Register new user account |
| `POST` | `/auth/login` | Authenticate, set httpOnly cookie, return JWT |
| `POST` | `/auth/logout` | Clear authentication cookie |
| `GET` | `/auth/me` | Get current user profile |

### Database Connections — `/connections`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/connections` | Register monitored PG connection (credentials encrypted at rest) |
| `GET` | `/connections` | List all active connections |
| `GET` | `/connections/{id}` | Get connection details |
| `POST` | `/connections/{id}/test` | Test reachability, permissions, extensions |
| `DELETE` | `/connections/{id}` | Remove monitored connection |
| `GET` | `/connections/{id}/telemetry` | Get live telemetry summary |
| `GET` | `/connections/{id}/diagnoses` | List diagnoses for connection |

### Diagnostics — `/diagnoses`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/diagnoses/{id}` | Full root-cause report with evidence graph |
| `GET` | `/diagnoses/{id}/recommendations` | Candidate optimizations for diagnosis |
| `POST` | `/diagnoses/{id}/investigate` | Trigger on-demand multi-agent investigation |

### Experiments & Verifications — `/experiments`, `/recommendations`, `/deployments`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/experiments` | List optimization experiments |
| `GET` | `/experiments/{id}` | Get experiment details |
| `POST` | `/recommendations/{id}/simulate` | Dispatch shadow DB simulation |
| `GET` | `/recommendations/{id}/verification` | Statistical verification result |
| `POST` | `/recommendations/{id}/approve` | Human approval for canary deployment |
| `POST` | `/recommendations/{id}/reject` | Reject recommendation (feeds bandit) |
| `GET` | `/deployments/{id}` | Canary deployment status |
| `GET` | `/experiments/{id}/canary/stream` | SSE stream — real-time canary metrics |

### Forecasting — `/forecast`, `/models`, `/forecasts`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/forecast/{connectionId}` | 7-day degradation risk forecast |
| `GET` | `/models/performance` | Model MAE/RMSE, calibration, drift reports |
| `GET` | `/forecasts/{id}/stream` | SSE stream — live forecast computation |

### ROI — `/roi`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/roi/{connectionId}` | Aggregate dollar savings per connection |
| `GET` | `/roi/experiments/{experimentId}` | ROI for specific experiment |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Service identity and status |
| `GET` | `/health` | Database connectivity health check |

### Interactive Docs

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/api/v1/openapi.json`

---

## Agent Modules

### Feature 1 — Root Cause Investigation

```mermaid
flowchart LR
    TRIGGER["Investigation Trigger"] --> PLANNER["Planner Agent"]
    TRIGGER --> IO["I/O Buffer Agent"]
    TRIGGER --> CONCURRENCY["Concurrency Agent"]
    TRIGGER --> VACUUM["Vacuum Agent"]
    TRIGGER --> SCHEMA["Schema Index Agent"]

    PLANNER --> EVIDENCE["Evidence Aggregation"]
    IO --> EVIDENCE
    CONCURRENCY --> EVIDENCE
    VACUUM --> EVIDENCE
    SCHEMA --> EVIDENCE

    EVIDENCE --> SUPERVISOR["Supervisor Agent"]
    SUPERVISOR --> DIAGNOSIS["Ranked Root Cause Report"]
```

| Agent | Domain | Investigates |
|-------|--------|-------------|
| **Planner Agent** | Query Plans | Plan regression, cardinality error, statistics freshness, plan flips |
| **I/O Buffer Agent** | Storage | Disk reads, buffer cache, WAL pressure, temp spill, checkpoints |
| **Concurrency Agent** | Locking | Blocking chains, lock waits, deadlocks, idle transactions |
| **Vacuum Agent** | Maintenance | Dead tuples, autovacuum lag, table bloat, vacuum backlog |
| **Schema Index Agent** | Schema | Missing indexes, unused indexes, wrong column order |
| **Supervisor Agent** | Reconciliation | Evidence weighting, contradiction resolution, causal ranking |

### Feature 2 — Safe Simulation & Verification

```mermaid
flowchart LR
    RECOMMEND["Recommendation"] --> EXP["Experiment Agent"]
    EXP --> SHADOW["Shadow DB Clone"]
    SHADOW --> REPLAY["Workload Replay"]
    REPLAY --> VERIFY["Verification Agent"]
    VERIFY --> ML_SCIENTIST["ML Scientist Agent"]
    VERIFY --> SKEPTIC["Skeptic Agent"]
    ML_SCIENTIST --> POLICY["Policy Agent"]
    SKEPTIC --> POLICY
    POLICY -->|VERIFIED| DEPLOY["Deployment Agent"]
    POLICY -->|REJECTED| REJECT["Rejection"]
    DEPLOY --> CANARY["Canary Window"]
    CANARY -->|PASS| COMMIT["Auto-Commit"]
    CANARY -->|FAIL| ROLLBACK["Auto-Rollback"]
```

| Agent | Role |
|-------|------|
| **Experiment Agent** | Creates shadow DB, installs candidate, runs replay, collects metrics |
| **Skeptic Agent** | Adversarial — searches for regressions, writes overhead, edge cases |
| **ML Scientist Agent** | Statistical significance testing (p-values, confidence intervals) |
| **Policy Agent** | Hard non-LLM-overridable safety rules and risk gates |
| **Verification Agent** | Combines statistics + ML prediction + skeptic findings into verdict |
| **Deployment Agent** | Executes approved change, manages canary window, auto-rollback |

### Feature 3 — Predictive ML & Closed-Loop Learning

| Agent | Role |
|-------|------|
| **Forecasting/Planning Agent** | Reads ML predictions, triggers simulations, selects actions |
| **Learning Agent** | Collects experiment outcomes, triggers retraining, evaluates models |

---

## ML Pipeline

```mermaid
flowchart LR
    subgraph "L1: Anomaly Detection"
        ISO["Isolation Forest<br/>(scikit-learn)"]
    end

    subgraph "L2: Root Cause Classification"
        LG_RCA["LightGBM<br/>Multi-label Classifier"]
    end

    subgraph "L3: Forecasting"
        LG_FCAST["LightGBM<br/>Degradation Forecaster"]
        LSTM["LSTM Autoencoder<br/>(PyTorch)"]
    end

    subgraph "L4: Strategy Selection"
        TS["Thompson Sampling<br/>Contextual Bandit"]
    end

    subgraph "L5: Model Monitoring"
        EVIDENTLY["Evidently<br/>Drift Detection"]
        MLFLOW_TRACK["MLflow<br/>Experiment Tracking"]
    end

    TELEMETRY["Raw Telemetry"] --> ISO
    ISO --> ANOMALY_SCORES["Anomaly Scores"]
    ANOMALY_SCORES --> LG_RCA
    LG_RCA --> DIAG["Root Cause Classes"]
    TELEMETRY --> LG_FCAST
    LG_FCAST --> FORECAST["Degradation Probability"]
    TELEMETRY --> LSTM
    LSTM --> TEMPORAL["Next-Window Anomaly"]
    EXPERIMENTS["Verified Experiments"] --> TS
    TS --> STRATEGY["Optimal Strategy"]
    PREDICTIONS["Model Predictions"] --> EVIDENTLY
    EVIDENTLY --> DRIFT["Drift Reports"]
    DRIFT --> RETRAIN["Retraining Trigger"]
    RETRAIN --> MLFLOW_TRACK
```

### Models

| Model | Library | Purpose |
|-------|---------|---------|
| Isolation Forest | scikit-learn | Multivariate anomaly scoring over ~17 features |
| LSTM Autoencoder | PyTorch | Temporal anomaly probability over 30-60 min windows |
| LightGBM (RCA) | LightGBM | Multi-label root cause classification |
| LightGBM (Forecast) | LightGBM | 7-day degradation probability forecasting |
| LightGBM (Delta) | LightGBM | Query performance delta prediction |
| Thompson Sampling | Custom | Contextual bandit for strategy selection |

### Training Data

Self-generated via a **Database Fault Laboratory**:
- Docker PostgreSQL + `pgbench` workload generator
- Fault injector: stale stats, plan regression, skew, lock contention, vacuum starvation, index problems, I/O pressure
- Ground-truth recorder captures labeled outcomes
- Walk-forward temporal split (no random shuffling)

---

## Database Schema

```mermaid
erDiagram
    users ||--o{ database_connections : owns
    users ||--o{ approvals : reviews
    users ||--o{ audit_logs : generates
    database_connections ||--o{ query_metrics : tracks
    database_connections ||--o{ table_metrics : monitors
    database_connections ||--o{ plan_metrics : records
    database_connections ||--o{ diagnoses : produces
    database_connections ||--o{ optimization_experiments : tests
    database_connections ||--o{ bandit_events : decisions
    database_connections ||--o{ forecast_records : forecasts
    database_connections ||--o{ roi_records : calculates
    database_connections ||--o{ canary_runs : deploys
    database_connections ||--o{ audit_logs : audited

    diagnoses ||--o{ evidence_graph_nodes : contains
    evidence_graph_nodes ||--o{ evidence_graph_edges : connects

    optimization_experiments ||--o{ model_predictions : predicts
    optimization_experiments ||--o{ bandit_events : selects
    optimization_experiments ||--o{ roi_records : translates
    optimization_experiments ||--o{ canary_runs : deploys
    optimization_experiments ||--o{ approvals : requires

    query_metrics ||--o{ plan_metrics : explains
```

### Tables (18 total)

| Table | Purpose |
|-------|---------|
| `users` | Application user accounts with roles and permissions |
| `database_connections` | Monitored PG connections with Fernet-encrypted credentials |
| `query_metrics` | `pg_stat_statements` snapshots (latency, I/O, WAL) |
| `table_metrics` | `pg_stat_user_tables` (row counts, dead tuples, vacuum timestamps) |
| `plan_metrics` | `EXPLAIN` plan structures, estimated vs actual rows |
| `diagnoses` | Root cause diagnosis records from supervisor agent |
| `evidence_graph_nodes` | Graph nodes: metrics, anomalies, hypotheses, root causes |
| `evidence_graph_edges` | Directed edges between evidence graph nodes |
| `optimization_experiments` | Simulation experiments (baseline vs candidate) |
| `model_predictions` | ML inference results and error tracking |
| `bandit_events` | Thompson Sampling strategy selection decisions |
| `forecast_records` | Degradation probability forecasts |
| `model_drift_reports` | Evidently data/prediction drift monitoring |
| `roi_records` | Dollar ROI calculations from verified experiments |
| `approvals` | Human approve/reject gates for production changes |
| `audit_logs` | Immutable audit trail for all security and DB-modifying events |
| `canary_runs` | Live canary observation windows with auto-rollback |

---

## Authentication & Security

### Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB

    Client->>API: POST /auth/login {email, password}
    API->>DB: SELECT user WHERE email = ?
    DB-->>API: user record
    API->>API: bcrypt.checkpw(password, hashed_password)
    API->>API: create_access_token(user_id, role, email)
    API->>API: Set httpOnly secure cookie
    API-->>Client: {access_token, user}
    
    Note over Client,API: Subsequent requests
    
    Client->>API: GET /api/v1/connections (Cookie: access_token=...)
    API->>API: Extract JWT from httpOnly cookie
    API->>API: decode_access_token()
    API->>DB: SELECT user WHERE id = ?
    DB-->>API: user record
    API->>API: Verify is_active
    API->>Route: Inject current_user
```

### Security Measures

| Layer | Implementation |
|-------|---------------|
| **Password Hashing** | bcrypt with securely generated salt |
| **JWT Tokens** | HS256, 24h expiry, httpOnly secure cookie |
| **Token Extraction** | Cookie first (httpOnly), then Bearer header fallback |
| **Credential Encryption** | Fernet (AES-128-CBC) for customer DB credentials at rest |
| **Decryption** | Just-in-time, never logged |
| **RBAC** | `role` field: `dba`, `admin`, `viewer`; `is_superuser` for admin endpoints |
| **Ownership** | Connection resources scoped to user; superusers see all |
| **CORS** | Configured for localhost dev origins with credentials |
| **Session Management** | Auto-commit/rollback with guaranteed session closure |
| **Audit Trail** | Immutable `audit_logs` table for all security events |

### Password & Credential Management

```python
# Hashing
hashed = hash_password("plaintext")    # bcrypt salt + hash
verify_password("plaintext", hashed)    # True / False

# Encryption
encrypted = encrypt_connection_string("postgresql://user:pass@host/db")
# Stored in DB — never logged, never returned in API

decrypted = decrypt_connection_string(encrypted)
# Used only in-memory, just-in-time
```

---

## Configuration

Settings are loaded via `pydantic-settings` from environment variables and `.env` files, searched in order:
1. `.env`
2. `apps/backend/.env`
3. `../.env`
4. `../../.env`

### Key Config Files

| File | Purpose |
|------|---------|
| `app/core/config.py` | Centralized Pydantic Settings with validation |
| `alembic.ini` | Alembic migration config |
| `docker-compose.yml` | Multi-service orchestration |
| `.env.example` | Environment variable template |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | Execution environment (`development`, `production`, `test`) |
| `PROJECT_NAME` | No | `Zentrix.ai` | Application name |
| `API_V1_PREFIX` | No | `/api/v1` | API route prefix |
| `API_PORT` | No | `8000` | Backend HTTP port |
| `APP_DATABASE_URL` | **Yes** | — | Async PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `JWT_SECRET_KEY` | **Yes** | — | Secret key for JWT signing (HS256) |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRY_MINUTES` | No | `1440` | JWT token lifetime (default 24h) |
| `CONNECTION_ENCRYPTION_KEY` | **Yes** | — | Fernet key for AES encryption of customer credentials |
| `MLFLOW_TRACKING_URI` | No | `http://localhost:5000` | MLflow tracking server URI |
| `TELEMETRY_POLL_INTERVAL_SECONDS` | No | `60` | Telemetry collector polling frequency |
| `CANARY_MONITOR_WINDOW_MINUTES` | No | `15` | Canary observation window before auto-commit/rollback |
| `SHADOW_DB_IMAGE` | No | `zentrix-shadow-db:latest` | Docker image for shadow DB containers |

### Generating a Fernet Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ (with `pg_stat_statements` extension)
- pip or conda
- Docker (for shadow DB and local development)

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/zentrix.ai.git
cd zentrix.ai

# Navigate to backend
cd apps/backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp ../../.env.example .env
# Edit .env with your real values

# Run database migrations
cd ../..
alembic upgrade head

# Start the server
cd apps/backend
uvicorn app.main:app --reload --port 8000
```

---

## Development

### Running Locally

```bash
# Start backend with hot-reload
cd apps/backend
uvicorn app.main:app --reload --port 8000

# Or from project root
make dev
```

### Linting & Formatting

```bash
# Lint
cd apps/backend
python -m ruff check .

# Format
cd apps/backend
python -m ruff format .

# Or from project root
make lint
make format
```

### Available Make Targets

| Command | Description |
|---------|-------------|
| `make dev` | Start backend + frontend dev servers |
| `make up` | `docker-compose up -d` |
| `make down` | `docker-compose down` |
| `make build` | `docker-compose build` |
| `make lint` | Run linters for frontend and backend |
| `make format` | Format code for frontend and backend |
| `make test` | Run tests for frontend and backend |
| `make clean` | Remove caches, `__pycache__`, `node_modules`, build artifacts |

---

## Running the Server

### Development

```bash
uvicorn app.main:app --reload --port 8000
```

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Verify

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

---

## Database Migrations

Alembic is configured for async PostgreSQL via `asyncpg`.

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Rollback one step
alembic downgrade -1

# View current revision
alembic current
```

Migration files are located in `migrations/versions/`.

---

## Testing

### Run All Tests

```bash
# From backend directory
python -m pytest

# Or from project root
make test
```

### Run Specific Test Suites

```bash
# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Specific test file
python -m pytest tests/unit/test_security.py -v
```

### Test Coverage

| Suite | Files | Description |
|-------|-------|-------------|
| Unit | 11 files | Config, security, DB session, schemas, models, logging, tools, services |
| Integration | 9 files | API skeleton, auth flow, connections, diagnosis, simulation, forecast, ROI, customer DB, approval gate |

---

## Docker

### Docker Compose Services

```mermaid
graph TD
    subgraph "Application Stack"
        BACKEND["backend<br/>:8000"]
        FRONTEND["frontend<br/>:3000"]
    end

    subgraph "Database"
        APP_DB["app-db<br/>PostgreSQL 16<br/>:5432"]
    end

    subgraph "Workers"
        TELEMETRY_W["telemetry-collector"]
        RETRAIN_W["retrain-worker"]
        CANARY_W["canary-monitor"]
        SHADOW_W["shadow-lab-worker"]
    end

    subgraph "ML Infrastructure"
        MLFLOW_S["mlflow<br/>:5000"]
    end

    BACKEND --> APP_DB
    FRONTEND --> BACKEND
    TELEMETRY_W --> APP_DB
    RETRAIN_W --> APP_DB
    CANARY_W --> APP_DB
    SHADOW_W --> APP_DB
    BACKEND --> MLFLOW_S
```

### Start All Services

```bash
docker-compose up -d
```

### Individual Services

| Service | Port | Description |
|---------|------|-------------|
| `app-db` | 5432 | PostgreSQL 16 application database |
| `backend` | 8000 | FastAPI backend API |
| `frontend` | 3000 | Next.js dashboard |
| `mlflow` | 5000 | MLflow tracking server |
| `telemetry-collector` | — | Polls customer databases for metrics |
| `retrain-worker` | — | Scheduled ML model retraining |
| `canary-monitor` | — | Observes canary deployments |
| `shadow-lab-worker` | — | Manages shadow DB containers |

---

## Deployment

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Generate strong `JWT_SECRET_KEY` (min 256-bit)
- [ ] Generate unique `CONNECTION_ENCRYPTION_KEY` (Fernet)
- [ ] Use managed PostgreSQL with SSL
- [ ] Configure CORS origins for production domain only
- [ ] Enable `secure=True` on cookies (HTTPS)
- [ ] Set up MLflow tracking server
- [ ] Configure log aggregation (JSON format auto-enabled in production)
- [ ] Run Alembic migrations before startup
- [ ] Set up monitoring (Prometheus/Grafana recommended)
- [ ] Configure worker scaling for telemetry collection

### Environment Profiles

| Profile | `ENVIRONMENT` | Log Format | Cookie Security | CORS |
|---------|--------------|------------|-----------------|------|
| Development | `development` | Human-readable | `secure=False` | Localhost only |
| Production | `production` | Structured JSON | `secure=True` | Custom domain |
| Test | `test` | Human-readable | `secure=False` | Localhost only |

---

## Performance Optimizations

| Area | Implementation |
|------|---------------|
| **Async I/O** | Full async/await stack — FastAPI, SQLAlchemy, asyncpg |
| **Connection Pooling** | SQLAlchemy pool for app DB; singleton asyncpg pools per customer DB |
| **Lazy Pool Creation** | Customer pools created on-demand, cached, reused |
| **Session Management** | Auto-commit/rollback with guaranteed cleanup |
| **Health Checks** | Lightweight `SELECT 1` ping on startup |
| **Structured Logging** | JSON in production for machine parsing, minimal overhead |
| **SSE Streaming** | Server-Sent Events for real-time updates without WebSocket complexity |
| **Settings Singleton** | `@lru_cache` for one-time config loading |
| **Dual Log Formatters** | Zero-overhead dev mode; production JSON without formatting cost |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards

- Python 3.12+ with type hints
- Ruff for linting and formatting
- Pydantic v2 for all schemas
- SQLAlchemy 2.0 async patterns
- `pytest` + `pytest-asyncio` for testing
- No comments unless architecture requires explanation

---

## License

This project is licensed under the MIT License — see the [LICENSE](../../LICENSE) file for details.

---

<div align="center">

**Built with precision for PostgreSQL intelligence**

Zentrix.ai — From telemetry to transformation, with evidence at every step.

</div>
