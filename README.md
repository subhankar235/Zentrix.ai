<div align="center">

# Zentrix.ai

**Autonomous Agentic Database Intelligence & Optimization Platform**

An AI-native system that continuously observes PostgreSQL databases, investigates root causes of performance issues, safely verifies optimization strategies, predicts future degradation, and learns from outcomes.

![Zentrix Hero](apps/frontend/Hero.png)

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.8-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.70-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Table of Contents

- [What is Zentrix](#what-is-zentrix)
- [How It Works](#how-it-works)
- [Core Capabilities](#core-capabilities)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Development](#development)
- [Docker](#docker)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## What is Zentrix

Traditional database monitoring tells you:

> "This query is slow."

Zentrix determines:

> **Why is it slow? What evidence supports that diagnosis? What optimization should be applied? Can we safely test it before production? Did it actually improve the database? And can the system learn from that outcome?**

The system combines **PostgreSQL internals, observability, machine learning, multi-agent reasoning, safe experimentation, causal verification, and closed-loop learning** into a single autonomous platform.

### Design Philosophy

```
Deterministic evidence pipeline first, ML second, LLM/agents last.
```

The LLM never invents facts or executes SQL directly. It reasons over structured evidence produced by collectors, statistical engines, and trained models.

---

## How It Works

```mermaid
flowchart TD
    A["1. Connect PostgreSQL"] --> B["2. Collect Telemetry"]
    B --> C["3. Detect Anomalies"]
    C --> D["4. Investigate Root Cause"]
    D --> E["5. Generate Optimization"]
    E --> F["6. Simulate on Shadow DB"]
    F --> G["7. Verify Statistically"]
    G --> H{"8. Safe?"}
    H -->|Yes| I["9. Human Approval"]
    H -->|No| J["9. Reject / Revise"]
    I --> K["10. Canary Deployment"]
    K --> L["11. Monitor Outcome"]
    L --> M["12. Feed Back to ML"]
    M --> B
    J --> E
```

### User Flow

1. **Sign up** and connect your PostgreSQL database (Neon, RDS, Supabase, or self-hosted)
2. **Telemetry Collector** polls `pg_stat_statements`, `pg_stat_activity`, and system views
3. **Deterministic Evidence Engine** computes cardinality error, plan diffs, lock chains, vacuum lag
4. **ML Layer** scores anomalies (Isolation Forest) and classifies root causes (LightGBM)
5. **Specialized Agents** (LangGraph) investigate plan regressions, I/O, locks, vacuum, schema
6. **Supervisor Agent** reconciles evidence into a ranked root-cause diagnosis
7. **Simulation Sandbox** tests optimizations on shadow databases with production workload replay
8. **Statistical Verification** validates results with p-values, confidence intervals, skeptic review
9. **Human Approval** gate before any production change
10. **Canary Deployment** with observation window and auto-rollback on regression
11. **Closed-Loop Learning** feeds outcomes back into ML models

---

## Core Capabilities

### 1. Multi-Agent Root Cause Investigation

Six specialized LangGraph agents independently investigate database problems:

| Agent | Domain | Investigates |
|-------|--------|-------------|
| Planner Agent | Query Plans | Plan regression, cardinality error, statistics freshness |
| I/O Buffer Agent | Storage | Disk reads, buffer cache, WAL pressure, temp spill |
| Concurrency Agent | Locking | Blocking chains, lock waits, deadlocks, idle transactions |
| Vacuum Agent | Maintenance | Dead tuples, autovacuum lag, table bloat |
| Schema Index Agent | Schema | Missing indexes, unused indexes, wrong column order |
| Supervisor Agent | Reconciliation | Evidence weighting, contradiction resolution, causal ranking |

### 2. Safe Simulation & Verification Sandbox

- Shadow DB cloning via `pg_dump`/`pg_restore`
- HypoPG virtual index simulation
- Production workload replay
- Statistical significance testing (p-values, confidence intervals)
- Adversarial Skeptic agent challenges
- Deterministic Policy engine safety gates

### 3. Predictive ML & Closed-Loop Learning

- **Isolation Forest** — multivariate anomaly detection over ~17 features
- **LSTM Autoencoder** — temporal anomaly probability over 30-60 min windows
- **LightGBM** — root cause classification and degradation forecasting
- **Thompson Sampling** — contextual bandit for optimization strategy selection
- **Evidently** — data and prediction drift monitoring
- **MLflow** — experiment tracking and model registry

### 4. Cost-to-Dollar ROI Translation

Deterministic calculation converting verified performance deltas into estimated dollar savings using cloud provider pricing lookup tables.

---

## Architecture

```mermaid
graph TD
    subgraph "Frontend"
        FE["Next.js 16 Dashboard"]
    end

    subgraph "Backend - FastAPI"
        API["REST API + SSE Streams"]
        AUTH["JWT Auth + RBAC"]
    end

    subgraph "Agent Layer - LangGraph"
        DIAG["Diagnosis Graph"]
        SIM["Simulation Graph"]
        FORECAST["Forecast Graph"]
        SUP["Supervisor"]
    end

    subgraph "ML Pipeline"
        ISO["Isolation Forest"]
        LG["LightGBM"]
        LSTM_M["LSTM Autoencoder"]
        TS["Thompson Sampling"]
        EV["Evidently Drift"]
    end

    subgraph "Tools"
        PG["PG Introspection"]
        PL["Policy Engine"]
        HP["HypoPG"]
        SD["Shadow DB"]
    end

    subgraph "Data"
        ADB[("App DB")]
        CDB[("Customer DB")]
        MF["MLflow"]
    end

    subgraph "Workers"
        TC["Telemetry Collector"]
        SLW["Shadow Lab"]
        RW["Retrain Worker"]
        CM["Canary Monitor"]
    end

    FE --> API
    API --> AUTH
    API --> DIAG
    API --> SIM
    API --> FORECAST
    DIAG --> SUP
    SIM --> SUP
    FORECAST --> SUP
    DIAG --> ISO
    DIAG --> LG
    FORECAST --> LG
    SIM --> TS
    SIM --> PL
    SIM --> HP
    SIM --> SD
    API --> ADB
    TC --> CDB
    CM --> CDB
    LG --> MF
    EV --> RW
```

---

## Technology Stack

### Backend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.12 | Core backend and ML |
| Framework | FastAPI 0.115.8 | Async REST API |
| ORM | SQLAlchemy 2.0 (async) | Database access |
| Driver | asyncpg | PostgreSQL async driver |
| Migrations | Alembic | Schema management |
| Validation | Pydantic v2 | Request/response schemas |
| Auth | PyJWT + bcrypt | JWT tokens + password hashing |
| Encryption | Fernet (AES) | Credential encryption at rest |
| Agents | LangGraph 0.2.70 | Multi-agent orchestration |
| ML | LightGBM, scikit-learn, PyTorch | Anomaly detection, classification, forecasting |
| Tracking | MLflow | Experiment and model registry |
| Drift | Evidently | Data/prediction drift monitoring |
| Data | NumPy, Pandas, Polars, DuckDB | Processing and analytics |

### Frontend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | Next.js 16.3.1 | React App Router |
| UI Library | React 19.2.8 | Component rendering |
| Language | TypeScript 5 | Type safety |
| Styling | Tailwind CSS v4 | Utility-first CSS |
| Components | shadcn/ui + Radix UI | Headless UI primitives |
| Charts | Recharts 3.10 | Data visualization |
| Animation | Framer Motion | Landing page animations |
| State | Zustand | Global state (theme) |
| Icons | Lucide React | Icon library |

### Infrastructure

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Database | PostgreSQL 16 | Application + target DB |
| Containerization | Docker + Compose | Local development |
| CI/CD | GitHub Actions | Automated pipelines |
| Monitoring | Prometheus + Grafana | Observability |
| Tracing | OpenTelemetry | Distributed tracing |

---

## Project Structure

```
zentrix.ai/
|
|-- apps/
|   |-- backend/                        # Python FastAPI backend
|   |   |-- app/
|   |   |   |-- main.py                 # FastAPI entry point
|   |   |   |-- core/                   # Config, security, logging
|   |   |   |-- db/                     # Database sessions, customer pools
|   |   |   |-- models/                 # SQLAlchemy ORM (18 tables)
|   |   |   |-- schemas/                # Pydantic validation schemas
|   |   |   |-- api/                    # Routes and dependencies
|   |   |   |-- services/               # Business logic
|   |   |   |-- agents/                 # LangGraph multi-agent system
|   |   |   |-- tools/                  # Database tools (PG, HypoPG, Shadow)
|   |   |   |-- ml/                     # ML models (temporal, RCA, bandit)
|   |   |   +-- workers/                # Background async workers
|   |   |-- migrations/                 # Alembic migrations
|   |   |-- tests/                      # Unit + integration tests
|   |   |-- requirements.txt            # Python dependencies
|   |   +-- README.md                   # Backend documentation
|   |
|   +-- frontend/                       # Next.js React frontend
|       |-- app/                        # App Router pages (11 routes)
|       |-- components/                 # 45+ React components
|       |-- lib/                        # Utilities, mock data, formatters
|       |-- types/                      # TypeScript interfaces
|       |-- stores/                     # Zustand stores
|       |-- styles/                     # Design system (oklch tokens)
|       |-- hooks/                      # Custom React hooks
|       |-- Hero.png                    # Hero image
|       |-- package.json                # Node dependencies
|       +-- README.md                   # Frontend documentation
|
|-- infra/
|   |-- docker/                         # Dockerfiles
|   +-- monitoring/                     # MLflow config
|
|-- DOCS/                               # Architecture, PRD, tech stack docs
|-- docker-compose.yml                  # Full stack orchestration
|-- Makefile                            # Dev commands (dev, up, down, lint, test)
|-- .env.example                        # Environment variable template
+-- LICENSE                             # MIT License
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ (or use Neon/Supabase)
- Docker (optional, for full stack)

### 1. Clone & Install

```bash
git clone https://github.com/your-org/zentrix.ai.git
cd zentrix.ai

# Backend
cd apps/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

Required variables:

```env
APP_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/zentrix
JWT_SECRET_KEY=your-secret-key
CONNECTION_ENCRYPTION_KEY=your-fernet-key
```

### 3. Run Database Migrations

```bash
cd apps/backend
alembic upgrade head
```

### 4. Start Development Servers

```bash
# From project root
make dev

# Or individually
cd apps/backend && uvicorn app.main:app --reload --port 8000 &
cd apps/frontend && npm run dev &
```

### 5. Open

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Development

### Available Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start backend + frontend dev servers |
| `make up` | `docker-compose up -d` |
| `make down` | `docker-compose down` |
| `make build` | `docker-compose build` |
| `make lint` | Run linters (ruff + eslint) |
| `make format` | Format code (ruff + prettier) |
| `make test` | Run tests (pytest + npm test) |
| `make clean` | Remove caches and build artifacts |

### Backend Commands

```bash
cd apps/backend

# Run server
uvicorn app.main:app --reload --port 8000

# Lint
python -m ruff check .

# Format
python -m ruff format .

# Test
python -m pytest

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Frontend Commands

```bash
cd apps/frontend

# Dev server
npm run dev

# Build
npm run build

# Start production
npm run start

# Lint
npm run lint
```

---

## Docker

### Full Stack

```bash
docker-compose up -d
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| `app-db` | 5432 | PostgreSQL 16 application database |
| `backend` | 8000 | FastAPI backend API |
| `frontend` | 3000 | Next.js dashboard |
| `mlflow` | 5000 | MLflow tracking server |
| `telemetry-collector` | — | Polls customer databases |
| `retrain-worker` | — | Scheduled ML retraining |
| `canary-monitor` | — | Observes canary deployments |
| `shadow-lab-worker` | — | Manages shadow DB containers |

---

## Documentation

| Document | Location | Description |
|----------|----------|-------------|
| [Backend README](apps/backend/README.md) | `apps/backend/` | Backend architecture, API endpoints, database schema, security |
| [Frontend README](apps/frontend/README.md) | `apps/frontend/` | Frontend architecture, components, design system, routes |
| [Architecture](DOCS/architecture.md) | `DOCS/` | System architecture document |
| [PRD](DOCS/prd.md) | `DOCS/` | Product requirements document |
| [Tech Stack](DOCS/techstack.md) | `DOCS/` | Technology stack decisions |
| [Backend Steps](DOCS/Backend steps.md) | `DOCS/` | Backend implementation steps |
| [Frontend Steps](DOCS/frontend_steps.md) | `DOCS/` | Frontend implementation steps |

---

## Roadmap

### Phase 1 — Foundation ✅
- [x] Project scaffolding (monorepo, Docker, CI)
- [x] Database schema (18 tables, Alembic migrations)
- [x] Authentication (JWT, bcrypt, httpOnly cookies)
- [x] API routes (6 groups, 25+ endpoints)
- [x] Frontend UI (11 routes, 45+ components)

### Phase 2 — Intelligence Engine
- [ ] Telemetry collector worker
- [ ] PG introspection tools
- [ ] Deterministic evidence engine
- [ ] Isolation Forest anomaly detection
- [ ] LightGBM root cause classifier

### Phase 3 — Agent Orchestration
- [ ] LangGraph diagnosis graph (6 agents)
- [ ] LangGraph simulation graph (6 agents)
- [ ] LangGraph forecast graph (2 agents)
- [ ] LLM client integration
- [ ] Evidence graph construction

### Phase 4 — Simulation & Verification
- [ ] Shadow DB cloning (Docker)
- [ ] HypoPG integration
- [ ] Workload replay engine
- [ ] Statistical verification
- [ ] Policy engine

### Phase 5 — Prediction & Learning
- [ ] Time-series forecasting (LightGBM + LSTM)
- [ ] Thompson Sampling bandit
- [ ] Closed-loop retraining
- [ ] Drift detection (Evidently)
- [ ] MLflow experiment tracking

### Phase 6 — Production
- [ ] Canary deployment with auto-rollback
- [ ] ROI translation engine
- [ ] Background worker scaling
- [ ] Monitoring & alerting
- [ ] Production hardening

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards

- **Backend**: Python 3.12+, Ruff for linting/formatting, Pydantic v2, SQLAlchemy async
- **Frontend**: TypeScript strict, ESLint, Tailwind CSS, shadcn/ui components
- **Commits**: Conventional commits preferred
- **Tests**: Write tests for new features

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with precision for PostgreSQL intelligence**

Zentrix.ai — From telemetry to transformation, with evidence at every step.

[Backend](apps/backend/README.md) · [Frontend](apps/frontend/README.md) · [Architecture](DOCS/architecture.md)

</div>
