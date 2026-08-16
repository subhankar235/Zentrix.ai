# DB Agent — Autonomous PostgreSQL Intelligence & Optimization Platform

> **An AI-native Database Reliability & Optimization Agent that continuously observes PostgreSQL, investigates root causes, safely verifies optimization strategies, predicts future performance problems, and learns from the results.**

DB Agent is an autonomous database intelligence platform designed to go beyond traditional database monitoring dashboards and static query advisors.

Instead of simply telling an engineer:

> “This query is slow.”

the system attempts to determine:

> **Why is it slow? What evidence supports that diagnosis? What optimization should be applied? Can we safely test it before production? Did it actually improve the database? And can the system learn from that outcome?**

The platform combines **PostgreSQL internals, observability, machine learning, multi-agent reasoning, safe experimentation, causal verification, and closed-loop learning** into a single system.

---

## Table of Contents

* [Vision](#vision)
* [Problem](#problem)
* [Core Capabilities](#core-capabilities)
* [How It Is Different](#how-it-is-different)
* [System Workflow](#system-workflow)
* [Feature 1 — Multi-Agent Root Cause Investigation](#feature-1--multi-agent-root-cause-investigation)
* [Feature 2 — Safe Simulation & Verification Sandbox](#feature-2--safe-simulation--verification-sandbox)
* [Feature 3 — Predictive ML Optimization & Closed-Loop Learning](#feature-3--predictive-ml-optimization--closed-loop-learning)
* [Architecture](#architecture)
* [Technology Stack](#technology-stack)
* [Data Collection](#data-collection)
* [AI / ML Architecture](#ai--ml-architecture)
* [Agent Architecture](#agent-architecture)
* [Optimization Lifecycle](#optimization-lifecycle)
* [Safety Model](#safety-model)
* [Database Connectivity](#database-connectivity)
* [PostgreSQL Intelligence](#postgresql-intelligence)
* [Observability](#observability)
* [Project Structure](#project-structure)
* [Development Setup](#development-setup)
* [Environment Variables](#environment-variables)
* [Running the System](#running-the-system)
* [Development Phases](#development-phases)
* [Example Investigation](#example-investigation)
* [Example Optimization](#example-optimization)
* [Security](#security)
* [Production Architecture](#production-architecture)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
* [License](#license)

---

# Vision

DB Agent aims to become an **autonomous DBA intelligence layer for PostgreSQL**.

Traditional database tooling is generally divided into separate categories:

```text
Monitoring
    ↓
Alerting
    ↓
Manual Investigation
    ↓
Manual Optimization
    ↓
Manual Verification
```

DB Agent turns this into a continuous feedback system:

```text
                ┌──────────────────────┐
                │      PostgreSQL      │
                └──────────┬───────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Telemetry Engine  │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Feature / ML      │
                 │ Intelligence      │
                 └─────────┬─────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │ Root Cause Investigation │
              │     Multi-Agent System   │
              └────────────┬─────────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Optimization      │
                 │ Strategy Engine   │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Safe Verification │
                 │ Sandbox           │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Production Change │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Outcome Analysis  │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Learning System   │
                 └─────────┬─────────┘
                           │
                           └──────────────► Future Decisions
```

The important concept is that **the system does not stop at recommendation**.

It measures whether the recommendation worked.

---

# Problem

Modern PostgreSQL systems can degrade for many different reasons:

* inefficient query plans
* missing indexes
* unused or poorly designed indexes
* stale statistics
* incorrect cardinality estimates
* plan regressions
* lock contention
* transaction contention
* connection saturation
* buffer-cache pressure
* disk I/O
* high WAL generation
* autovacuum delays
* table/index bloat
* dead tuples
* checkpoint pressure
* memory pressure
* workload pattern changes
* sudden traffic growth
* parameter-sensitive queries
* schema changes
* changing data distributions

A traditional monitoring system may detect:

```text
Query latency increased from 200ms → 4.8s
```

But that does not answer:

```text
Why?
```

DB Agent attempts to build an evidence-backed explanation.

For example:

```text
Latency regression detected.

Evidence:

Query latency:
+680%

Rows returned:
+4%

Rows estimated:
1,200

Rows actually scanned:
1,840,000

Plan:
Index Scan → Sequential Scan

Statistics freshness:
Low

Table modification rate:
High

Autovacuum:
Delayed

Conclusion:
High-confidence stale-statistics-induced plan regression.

Recommended action:
ANALYZE orders;

Expected impact:
Reduced cardinality estimation error and restoration
of index-based execution plan.
```

---

# Core Capabilities

DB Agent is centered around three major capabilities.

## 1. Multi-Agent Root Cause Investigation

Investigates **why** a database problem happened.

The investigation engine combines multiple independent evidence sources:

* query statistics
* execution plans
* planner estimates
* buffer/cache behavior
* disk I/O
* locks
* transactions
* vacuum/autovacuum
* table/index statistics
* workload patterns

Multiple specialized agents independently investigate the problem before a supervisor reconciles their conclusions.

---

## 2. Safe Simulation & Verification Sandbox

Before changing production, DB Agent attempts to answer:

> “What happens if we apply this optimization?”

Potential strategies can include:

* index creation
* index removal
* query rewrite
* statistics refresh
* configuration changes
* vacuum/analyze recommendations
* partitioning recommendations
* connection/resource tuning

The system evaluates the proposed change in a controlled environment before production execution whenever possible.

The goal is:

```text
Recommendation
      ↓
Simulation
      ↓
Benchmark
      ↓
Verification
      ↓
Risk Assessment
      ↓
Production Approval
```

---

## 3. Predictive ML Optimization & Closed-Loop Learning

Instead of waiting for a database problem to occur, the system learns workload patterns and attempts to predict future degradation.

For example:

```text
Current workload:
Healthy

Trend:
CPU +8% / week
Query volume +13% / week
Table size +11% / week

Prediction:
orders table likely to cross
performance degradation threshold
within approximately 9–14 days.

Suggested preventive action:
Review index strategy + statistics + query plan.
```

After an optimization is executed, the system measures the result.

```text
Prediction
    ↓
Recommendation
    ↓
Optimization
    ↓
Observed Outcome
    ↓
Reward / Error
    ↓
Model Update
    ↓
Better Future Prediction
```

This creates a **closed-loop optimization flywheel**.

---

# How It Is Different

DB Agent is not intended to be another:

* SQL dashboard
* query viewer
* generic chatbot
* static index advisor
* simple alerting system
* LLM wrapper around PostgreSQL

The differentiator is the combination of:

```text
PostgreSQL Internals
        +
Observability
        +
Machine Learning
        +
Multi-Agent Investigation
        +
Safe Experimentation
        +
Outcome Verification
        +
Continuous Learning
```

The system should be able to distinguish between:

```text
Detection
    ≠
Diagnosis
    ≠
Recommendation
    ≠
Verification
    ≠
Learning
```

---

# System Workflow

A typical lifecycle looks like this:

```text
1. Connect PostgreSQL
        ↓
2. Collect telemetry
        ↓
3. Normalize metrics
        ↓
4. Detect anomalies
        ↓
5. Extract relevant evidence
        ↓
6. Start investigation
        ↓
7. Run specialized agents
        ↓
8. Supervisor reconciles evidence
        ↓
9. Generate root-cause hypothesis
        ↓
10. Generate optimization candidates
        ↓
11. Estimate risk / expected benefit
        ↓
12. Simulate or benchmark
        ↓
13. Verify expected improvement
        ↓
14. Request approval if required
        ↓
15. Apply optimization
        ↓
16. Monitor post-change behavior
        ↓
17. Compare before vs after
        ↓
18. Record outcome
        ↓
19. Update ML / decision models
        ↓
20. Improve future recommendations
```

---

# Feature 1 — Multi-Agent Root Cause Investigation

## Objective

Determine the **actual cause** of database performance degradation rather than simply identifying the slow query.

---

## Investigation Agents

### Planner / Statistics Agent

Investigates:

* query plans
* cardinality estimates
* estimated vs actual rows
* statistics freshness
* selectivity
* planner behavior
* plan changes
* sequential scans
* index scans
* join strategy

Example hypothesis:

```text
Planner estimates 1,500 rows
but execution observes 1,800,000 rows.

Estimated/actual ratio ≈ 1:1200.

Likely cause:
statistics / distribution mismatch.
```

---

### I/O Agent

Investigates:

* disk reads
* buffer reads
* cache hit ratio
* read amplification
* sequential I/O
* random I/O
* WAL activity
* checkpoint behavior

Example:

```text
Query latency increased
+
shared buffer hits decreased
+
disk reads increased dramatically

Possible cause:
cache pressure / working-set expansion.
```

---

### Locking Agent

Investigates:

* blocked queries
* blocking sessions
* lock waits
* transaction duration
* deadlocks
* contention patterns
* idle transactions

Example:

```text
Query execution time:
180ms

Lock wait:
4.3s

Conclusion:
Database compute is not the primary bottleneck.
Transaction contention is.
```

---

### Vacuum Agent

Investigates:

* dead tuples
* autovacuum activity
* table growth
* vacuum lag
* analyze frequency
* transaction ID pressure
* bloat indicators

Example:

```text
Dead tuples:
+340%

Autovacuum:
falling behind

Table:
rapidly growing

Potential consequence:
larger scans + stale statistics + increased I/O.
```

---

### Workload Agent

Investigates workload-level behavior:

* query frequency
* traffic spikes
* new query patterns
* query distribution
* concurrency
* seasonal behavior
* workload drift

This agent is particularly important for predictive optimization.

---

## Supervisor Agent

The supervisor does not blindly trust a single agent.

It receives evidence from all investigators:

```text
Planner Agent
      │
I/O Agent
      │
Lock Agent
      ├──────► Supervisor
Vacuum Agent
      │
Workload Agent
```

The supervisor:

1. compares hypotheses
2. checks conflicting evidence
3. assigns confidence
4. removes unsupported explanations
5. identifies the strongest root cause
6. produces a structured diagnosis

Example:

```json
{
  "root_cause": "stale_statistics",
  "confidence": 0.91,
  "severity": "high",
  "evidence": [
    "large estimated-vs-actual row mismatch",
    "recent high table modification rate",
    "plan regression",
    "statistics not recently refreshed"
  ],
  "recommended_action": "ANALYZE orders"
}
```

---

# Feature 2 — Safe Simulation & Verification Sandbox

## Objective

Never allow an AI model to casually modify production.

The system separates:

```text
Recommendation
```

from:

```text
Execution
```

---

## Optimization Candidate Generation

The optimization engine can generate candidates such as:

```text
CREATE INDEX
DROP INDEX
ANALYZE
VACUUM
Query rewrite
Configuration adjustment
Partitioning strategy
Connection/resource tuning
```

Each candidate should contain:

```json
{
  "action": "...",
  "reason": "...",
  "expected_benefit": "...",
  "risk": "...",
  "rollback": "...",
  "verification_metric": "..."
}
```

---

## Simulation

Where feasible, the system tests the candidate against:

* representative workload
* query plans
* execution time
* buffer consumption
* I/O
* CPU
* row estimates
* concurrency behavior

For query-plan experiments, PostgreSQL capabilities such as `EXPLAIN`, `EXPLAIN ANALYZE`, planner settings, and isolated test environments can be used.

---

## Before / After Verification

The system stores a baseline:

```text
Before

p50 latency: 320ms
p95 latency: 1.8s
p99 latency: 4.7s
CPU: 71%
buffer hit ratio: 93%
```

After optimization:

```text
After

p50 latency: 140ms
p95 latency: 720ms
p99 latency: 1.4s
CPU: 54%
buffer hit ratio: 97%
```

The verifier calculates whether the improvement is statistically meaningful rather than assuming:

> “The query became faster once, therefore the optimization worked.”

---

## Verification Model

A change can be classified as:

```text
IMPROVED
NO_SIGNIFICANT_CHANGE
REGRESSED
INCONCLUSIVE
UNSAFE
```

The result becomes training/feedback data for the learning system.

---

# Feature 3 — Predictive ML Optimization & Closed-Loop Learning

## Objective

Predict database degradation before it becomes a production incident.

---

## Time-Series Signals

Potential features include:

* query latency
* query frequency
* CPU utilization
* memory pressure
* cache hit ratio
* disk throughput
* IOPS
* WAL volume
* table growth
* index growth
* dead tuples
* autovacuum delay
* lock wait time
* connection utilization
* rows scanned
* rows returned
* query-plan changes

---

## Anomaly Detection

The ML layer can detect unusual behavior using techniques such as:

* Isolation Forest
* robust statistical baselines
* rolling-window analysis
* clustering
* change-point detection
* time-series forecasting
* autoencoder-based anomaly detection where justified

The goal is not to use deep learning everywhere.

A simpler model should be preferred when it provides better reliability and explainability.

---

## Predictive Modeling

The system can estimate:

```text
P(performance_degradation | current workload trajectory)
```

or:

```text
Expected latency in next N hours/days
```

or:

```text
Probability that optimization X will improve workload Y
```

---

## Closed-Loop Learning

Every optimization produces an outcome.

```text
              ┌───────────────┐
              │ Prediction    │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ Recommendation│
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ Experiment    │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ Execute       │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ Measure       │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ Outcome       │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ Model Update  │
              └───────┬───────┘
                      │
                      └──────────► Future Predictions
```

This allows the system to learn:

```text
Which recommendations work?
For which workload?
Under which database conditions?
With what confidence?
At what cost?
```

---

# Architecture

The high-level architecture is:

```text
                         ┌──────────────────────┐
                         │      Web Console     │
                         │   Next.js / React    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      API Gateway     │
                         │       FastAPI        │
                         └──────────┬───────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                 │
                  ▼                 ▼                 ▼
          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
          │ Investigation│  │ Optimization │  │ Prediction   │
          │ Engine       │  │ Engine       │  │ Engine       │
          └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                 │                 │                 │
                 └─────────────────┼─────────────────┘
                                   ▼
                         ┌──────────────────────┐
                         │ Agent Orchestrator   │
                         │ LangGraph             │
                         └──────────┬───────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
        ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
        │ Planner     │     │ I/O Agent   │     │ Lock Agent  │
        └─────────────┘     └─────────────┘     └─────────────┘
                │                   │                   │
        ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
        │ Vacuum      │     │ Workload    │     │ Supervisor  │
        │ Agent       │     │ Agent       │     │ Agent       │
        └─────────────┘     └─────────────┘     └─────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ PostgreSQL Collector │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Target PostgreSQL    │
                         │ Local / Neon / Cloud │
                         └──────────────────────┘
```

---

# Technology Stack

## Frontend

| Technology         | Purpose                         |
| ------------------ | ------------------------------- |
| Next.js            | Web application                 |
| React              | UI                              |
| TypeScript         | Type safety                     |
| Tailwind CSS       | Styling                         |
| Recharts / ECharts | Metrics visualization           |
| TanStack Query     | Server state                    |
| WebSocket / SSE    | Real-time investigation updates |

---

## Backend

| Technology | Purpose                     |
| ---------- | --------------------------- |
| Python     | Core backend and ML         |
| FastAPI    | API layer                   |
| Pydantic   | Validation                  |
| SQLAlchemy | Application database access |
| Alembic    | Database migrations         |
| AsyncIO    | Concurrent workloads        |

---

## Agentic Layer

| Technology              | Purpose                       |
| ----------------------- | ----------------------------- |
| LangGraph               | Stateful agent orchestration  |
| LLM                     | Reasoning and explanation     |
| Structured Outputs      | Deterministic agent responses |
| Tool Calling            | Database inspection           |
| Supervisor architecture | Multi-agent reconciliation    |

The LLM is **not** given unrestricted database access.

Agents interact through controlled tools.

---

## Machine Learning

Potential stack:

| Technology         | Purpose                        |
| ------------------ | ------------------------------ |
| Python             | ML development                 |
| scikit-learn       | Classical ML                   |
| XGBoost / LightGBM | Predictive models              |
| PyTorch            | Advanced models when justified |
| pandas             | Dataset processing             |
| NumPy              | Numerical computation          |
| MLflow             | Experiment/model tracking      |
| SHAP               | Explainability                 |

The initial system should prioritize classical ML and statistical methods before introducing more complex models.

---

## Database

### Target Database

**PostgreSQL**

Supported deployment patterns can include:

```text
Local PostgreSQL
Docker PostgreSQL
Neon PostgreSQL
Managed PostgreSQL
Cloud PostgreSQL
```

### DB Agent Metadata Store

A separate PostgreSQL database can store:

* database connections
* collected metrics
* investigations
* hypotheses
* recommendations
* experiments
* optimization results
* model versions
* audit events

This prevents the target database from becoming the application's control-plane database.

---

## Vector Database

Optional:

```text
Qdrant
```

Useful for storing:

* historical investigation summaries
* database incidents
* optimization experiences
* runbooks
* schema context
* learned operational knowledge

Vector search should support the agent rather than replace deterministic database analysis.

---

## Infrastructure

| Technology     | Purpose                  |
| -------------- | ------------------------ |
| Docker         | Containerization         |
| Docker Compose | Local development        |
| Kubernetes     | Production orchestration |
| Terraform      | Infrastructure as Code   |
| GitHub Actions | CI/CD                    |
| Prometheus     | Metrics                  |
| Grafana        | Observability            |
| OpenTelemetry  | Distributed tracing      |

---

# Data Collection

The collector is one of the most important parts of the platform.

It should obtain information directly from PostgreSQL rather than relying exclusively on application APIs.

Potential PostgreSQL sources include:

```text
pg_stat_activity
pg_stat_statements
pg_locks
pg_stat_user_tables
pg_stat_user_indexes
pg_statio_user_tables
pg_statio_user_indexes
pg_database
pg_settings
pg_class
pg_index
pg_indexes
pg_stat_progress_vacuum
```

The collector converts raw PostgreSQL information into normalized observations.

Example:

```json
{
  "timestamp": "...",
  "database_id": "...",
  "query_id": "...",
  "latency_ms": 4820,
  "calls": 812,
  "rows": 1902,
  "shared_blks_hit": 12903,
  "shared_blks_read": 84211,
  "temp_blks_written": 9122
}
```

---

# AI / ML Architecture

The system intentionally separates deterministic computation from probabilistic reasoning.

```text
PostgreSQL
     ↓
Deterministic Collector
     ↓
Feature Engineering
     ↓
ML / Anomaly Detection
     ↓
Evidence Package
     ↓
LLM / Agent Reasoning
     ↓
Structured Diagnosis
```

The LLM should not calculate basic PostgreSQL metrics itself.

For example:

Bad:

```text
LLM:
"I think CPU is high."
```

Better:

```text
Collector:
CPU = 87%

Baseline:
CPU = 52%

Deviation:
+35 percentage points

Anomaly score:
0.94
```

Then the agent reasons over that evidence.

---

# Agent Architecture

Each agent should have a narrow responsibility.

```text
                     Supervisor
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
     Planner            I/O            Locking
        │                │                │
        └────────────────┼────────────────┘
                         │
                ┌────────┴────────┐
                ▼                 ▼
             Vacuum            Workload
                │                 │
                └────────┬────────┘
                         ▼
                  Final Diagnosis
```

Each agent should return structured information:

```json
{
  "agent": "planner",
  "hypotheses": [
    {
      "cause": "cardinality_misestimation",
      "confidence": 0.87,
      "evidence": [
        "estimated rows differ significantly from actual rows"
      ]
    }
  ]
}
```

This makes agent outputs machine-readable and auditable.

---

# Optimization Lifecycle

Every optimization should follow a controlled lifecycle.

```text
DISCOVER
   ↓
DIAGNOSE
   ↓
PROPOSE
   ↓
SIMULATE
   ↓
VERIFY
   ↓
APPROVE
   ↓
EXECUTE
   ↓
OBSERVE
   ↓
COMPARE
   ↓
LEARN
```

An optimization should never jump directly from:

```text
LLM recommendation
        ↓
production SQL
```

---

# Safety Model

Safety is a first-class architectural component.

## Read-Only by Default

The database collector should initially operate using read-only credentials.

The agent can inspect:

* queries
* plans
* statistics
* locks
* indexes
* table metadata

without modifying production.

---

## Explicit Write Permissions

Write operations should require a separate capability.

For example:

```text
READ
ANALYZE
SIMULATE
PROPOSE
APPROVE
EXECUTE
ROLLBACK
```

These permissions can be represented as separate capabilities.

---

## Human Approval

High-risk operations should require explicit approval.

Example:

```text
Optimization:
DROP INDEX idx_orders_customer

Expected benefit:
Low

Risk:
High

Reason:
Index is used by 3 important queries.

Recommendation:
DO NOT EXECUTE
```

---

## Rollback

Every mutation should have:

```text
Forward action
+
Rollback strategy
+
Verification criteria
+
Maximum risk
```

---

# Database Connectivity

The user experience should be simple.

```text
1. Open DB Agent
        ↓
2. Click "Connect Database"
        ↓
3. Select PostgreSQL
        ↓
4. Provide connection details
        ↓
5. DB Agent tests connection
        ↓
6. Verify permissions
        ↓
7. Discover PostgreSQL capabilities
        ↓
8. Start telemetry collection
        ↓
9. Dashboard becomes active
```

A connection can be represented as:

```text
PostgreSQL
├── Host
├── Port
├── Database
├── Username
└── Password / Secret
```

For Neon, the PostgreSQL connection string can be used directly.

The application should never expose database credentials to the frontend.

---

# PostgreSQL Intelligence

The system should understand PostgreSQL-specific behavior rather than treating PostgreSQL as a generic SQL database.

Important concepts include:

### Query Planning

```text
Seq Scan
Index Scan
Index Only Scan
Bitmap Heap Scan
Nested Loop
Hash Join
Merge Join
Sort
Aggregate
```

### Statistics

```text
pg_stat_statements
pg_stats
ANALYZE
cardinality estimates
selectivity
```

### Concurrency

```text
locks
blocking
deadlocks
transactions
idle transactions
```

### Maintenance

```text
VACUUM
AUTOVACUUM
ANALYZE
dead tuples
table bloat
index bloat
```

### Storage / I/O

```text
shared buffers
cache hits
disk reads
temporary files
WAL
checkpoints
```

This PostgreSQL-specific intelligence is a core part of the product.

---

# Observability

The DB Agent itself should be observable.

Important system metrics:

```text
agent investigation latency
agent success rate
ML prediction accuracy
recommendation acceptance rate
optimization success rate
false-positive rate
false-negative rate
sandbox execution time
database collector latency
API latency
LLM token usage
LLM cost
```

Most importantly:

```text
Recommendation → Outcome
```

should be measurable.

---

# Project Structure

A recommended monorepo structure:

```text
db-agent/
│
├── apps/
│   │
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── types/
│   │   └── package.json
│   │
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   ├── core/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   ├── repositories/
│       │   └── main.py
│       │
│       ├── agents/
│       │   ├── planner/
│       │   ├── io/
│       │   ├── locking/
│       │   ├── vacuum/
│       │   ├── workload/
│       │   └── supervisor/
│       │
│       ├── collectors/
│       │   ├── postgres/
│       │   ├── activity.py
│       │   ├── queries.py
│       │   ├── locks.py
│       │   ├── vacuum.py
│       │   └── indexes.py
│       │
│       ├── optimization/
│       │   ├── planner.py
│       │   ├── candidates.py
│       │   ├── simulator.py
│       │   ├── verifier.py
│       │   └── rollback.py
│       │
│       ├── ml/
│       │   ├── features/
│       │   ├── anomaly/
│       │   ├── forecasting/
│       │   ├── prediction/
│       │   ├── training/
│       │   └── evaluation/
│       │
│       └── tests/
│
├── packages/
│   ├── shared/
│   ├── schemas/
│   └── config/
│
├── ml/
│   ├── datasets/
│   ├── experiments/
│   ├── models/
│   └── notebooks/
│
├── infra/
│   ├── docker/
│   ├── kubernetes/
│   ├── terraform/
│   ├── prometheus/
│   └── grafana/
│
├── db/
│   └── migrations/
│
├── scripts/
│
├── tests/
│
├── docker-compose.yml
├── .env.example
├── package.json
├── turbo.json
└── README.md
```

---

# Development Setup

## Prerequisites

Install:

* Node.js
* Python 3.12+
* PostgreSQL
* Docker
* Git
* npm / pnpm
* optional Kubernetes tooling

Verify:

```bash
node --version
python --version
docker --version
git --version
```

---

# Environment Variables

Example:

```env
# Application
APP_ENV=development
API_PORT=8000
WEB_PORT=3000

# Application PostgreSQL
DATABASE_URL=postgresql+asyncpg://...

# Target PostgreSQL
TARGET_DATABASE_URL=postgresql://...

# LLM
OPENAI_API_KEY=...

# Agent framework
LANGCHAIN_API_KEY=...
LANGCHAIN_TRACING_V2=true

# Vector database
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=...

# ML tracking
MLFLOW_TRACKING_URI=http://localhost:5000

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Secrets should never be committed to Git.

Use:

```text
.env
```

locally and provide:

```text
.env.example
```

for configuration documentation.

---

# Running the System

## Backend

```bash
cd apps/api
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

---

## Frontend

```bash
cd apps/web
npm install
npm run dev
```

The frontend will normally run at:

```text
http://localhost:3000
```

The backend will normally run at:

```text
http://localhost:8000
```

---

# Development Phases

## Phase 1 — PostgreSQL Connection

Build:

* database connection manager
* connection testing
* permission detection
* PostgreSQL version detection
* extension detection

---

## Phase 2 — Telemetry Collector

Implement:

* `pg_stat_activity`
* `pg_stat_statements`
* `pg_locks`
* table statistics
* index statistics
* vacuum statistics
* I/O statistics

---

## Phase 3 — Observability Layer

Build:

* metric normalization
* historical storage
* baseline calculation
* anomaly detection
* time-series queries

---

## Phase 4 — Root Cause Engine

Build:

* planner agent
* I/O agent
* lock agent
* vacuum agent
* workload agent
* supervisor agent

---

## Phase 5 — Optimization Engine

Build:

* candidate generator
* index advisor
* query optimization recommendations
* statistics recommendations
* maintenance recommendations
* risk scoring

---

## Phase 6 — Sandbox

Build:

* isolated database environment
* workload replay
* benchmark runner
* before/after comparison
* rollback validation

---

## Phase 7 — Predictive ML

Build:

* feature engineering
* anomaly detection
* forecasting
* degradation prediction
* model evaluation

---

## Phase 8 — Closed-Loop Learning

Record:

```text
Problem
↓
Diagnosis
↓
Recommendation
↓
Experiment
↓
Execution
↓
Outcome
```

Use the collected outcomes to improve:

* prediction accuracy
* recommendation ranking
* confidence estimation
* risk estimation

---

# Example Investigation

Suppose a production query suddenly becomes slow.

The collector detects:

```text
Query:
SELECT * FROM orders
WHERE customer_id = $1;

Previous p95:
420ms

Current p95:
4.8s
```

The anomaly detector flags the change.

The investigation begins.

### Planner Agent

Finds:

```text
Estimated rows:
2,000

Actual rows:
1,700,000
```

### I/O Agent

Finds:

```text
Disk reads:
very high

Buffer hit ratio:
decreased
```

### Vacuum Agent

Finds:

```text
Table modification rate:
high

Statistics:
stale
```

### Lock Agent

Finds:

```text
No significant blocking.
```

### Supervisor

Combines the evidence:

```text
Root Cause:
Cardinality estimation failure caused by stale statistics.

Confidence:
93%

Primary evidence:
- huge estimated/actual row mismatch
- recent table modifications
- stale statistics
- plan regression
- no significant lock contention
```

The optimization engine recommends:

```sql
ANALYZE orders;
```

The sandbox tests the change.

The result:

```text
p95:
4.8s → 610ms

Rows estimate:
2,000 → 1,630,000

Execution plan:
Sequential Scan → Index Scan
```

The verifier marks:

```text
IMPROVED
```

The outcome is stored for future learning.

---

# Example Optimization

Consider a query:

```sql
SELECT *
FROM orders
WHERE customer_id = $1
ORDER BY created_at DESC
LIMIT 50;
```

The agent identifies:

```text
High frequency
+
High latency
+
Repeated sort operation
+
Large scanned row count
```

Candidate:

```sql
CREATE INDEX CONCURRENTLY
idx_orders_customer_created
ON orders(customer_id, created_at DESC);
```

Before executing, the system estimates:

```text
Expected latency:
900ms → <100ms

Expected storage cost:
+X GB

Risk:
Medium

Rollback:
DROP INDEX CONCURRENTLY ...
```

The sandbox tests the strategy.

If the result is positive:

```text
Latency:
870ms → 82ms

CPU:
-31%

Rows scanned:
-98%

Regression:
None detected
```

The optimization receives a high confidence score.

Production execution can then require human approval depending on policy.

---

# Security

DB Agent handles highly sensitive database information.

Security principles:

## Least Privilege

The collector should use read-only credentials whenever possible.

---

## Credential Isolation

Database passwords should:

* never be stored in frontend code
* never be logged
* never be returned through API responses
* never be committed to Git

---

## SQL Safety

AI-generated SQL should pass through:

```text
Parser
 ↓
Policy Engine
 ↓
Risk Classifier
 ↓
Sandbox
 ↓
Approval
 ↓
Execution
```

The LLM should never have arbitrary direct database access.

---

## Audit Trail

Every important operation should be recorded:

```text
who
what
when
why
database
query
agent
recommendation
approval
result
rollback
```

---

# Production Architecture

A production deployment can look like:

```text
                         Internet
                            │
                            ▼
                     Load Balancer
                            │
                            ▼
                    Next.js Frontend
                            │
                            ▼
                     FastAPI Gateway
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
         Agent Workers   ML Workers   API Workers
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                     Message / Job Layer
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
        PostgreSQL       Qdrant         MLflow
        Metadata DB      Knowledge       Models
             │
             ▼
      Target PostgreSQL
       / Neon / Cloud
```

For larger deployments, collectors and agent workers can scale independently.

---

# Roadmap

## Near Term

* [ ] PostgreSQL connection manager
* [ ] Secure credential handling
* [ ] PostgreSQL telemetry collector
* [ ] Query performance dashboard
* [ ] anomaly detection
* [ ] root-cause investigation
* [ ] multi-agent supervisor
* [ ] optimization recommendations

## Medium Term

* [ ] simulation sandbox
* [ ] workload replay
* [ ] before/after verification
* [ ] risk scoring
* [ ] automated rollback
* [ ] predictive workload models
* [ ] model evaluation pipeline

## Advanced

* [ ] closed-loop learning
* [ ] optimization outcome dataset
* [ ] recommendation ranking model
* [ ] adaptive risk model
* [ ] workload-specific optimization policies
* [ ] autonomous low-risk optimization
* [ ] multi-database support
* [ ] Kubernetes-native database intelligence
* [ ] cross-database learning

---

# Design Principles

DB Agent follows several important principles.

### 1. Evidence Before Reasoning

Collect reliable database evidence before asking an LLM to reason.

### 2. Diagnosis Before Optimization

Do not recommend an optimization without understanding the likely cause.

### 3. Simulation Before Production

Test risky changes before applying them whenever technically possible.

### 4. Measurement After Execution

An optimization is not considered successful merely because it executed successfully.

### 5. Learning From Outcomes

Every optimization creates valuable feedback.

### 6. Deterministic Systems Where Possible

Use SQL, statistics, metrics, parsers, and ML for measurable tasks.

Use LLMs primarily for:

* hypothesis generation
* evidence synthesis
* explanation
* planning
* multi-agent reasoning

### 7. Human Control Over High-Risk Actions

Autonomy should increase with evidence and decrease with risk.

---

# What DB Agent Ultimately Becomes

The long-term architecture is not simply:

```text
User → AI → Database
```

It is:

```text
                  ┌─────────────────────┐
                  │ PostgreSQL Workload │
                  └──────────┬──────────┘
                             ↓
                    Continuous Sensing
                             ↓
                    ML Anomaly Detection
                             ↓
                    Multi-Agent Diagnosis
                             ↓
                  Evidence-Based Planning
                             ↓
                    Safe Experimentation
                             ↓
                   Statistical Verification
                             ↓
                     Controlled Execution
                             ↓
                     Outcome Measurement
                             ↓
                    Continuous Learning
                             │
                             └──────────────┐
                                            ↓
                                  Better Future Decisions
```

The fundamental objective is:

> **Build a database agent that does not merely monitor PostgreSQL, but understands its behavior, investigates failures, predicts degradation, safely experiments with optimizations, verifies the results, and improves from its own operational history.**

---

# Status

**Project Type:** AI-native Database Reliability & Optimization Platform

**Primary Database:** PostgreSQL

**Primary Backend:** Python + FastAPI

**Agent Framework:** LangGraph

**ML:** scikit-learn / XGBoost / PyTorch where justified

**Frontend:** Next.js + React + TypeScript

**Observability:** OpenTelemetry + Prometheus + Grafana

**Vector Memory:** Qdrant

**Infrastructure:** Docker + Kubernetes + Terraform

**Target Deployments:** Local PostgreSQL, Neon, managed PostgreSQL, cloud PostgreSQL

**Core Differentiator:**

```text
Detect
  +
Diagnose
  +
Predict
  +
Simulate
  +
Verify
  +
Optimize
  +
Learn
```

---

# License

Choose a license appropriate for the intended open-source/commercial model of the project.

For example:

```text
MIT License
```

or a commercial/source-available license if the platform is intended to become a proprietary product.
