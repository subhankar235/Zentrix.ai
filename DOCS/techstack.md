
# TECHSTACK.md

> **Note on cost:** Every ML/AI model in this stack is open-source and free to run locally (scikit-learn, LightGBM, PyTorch, HypoPG, etc.) — no paid model API is required anywhere in the pipeline. The only place an LLM is used is inside the LangGraph agents for reasoning/report writing over already-computed evidence; any open-weight or already-available LLM works there.

## Overall Stack

An AI Database Administrator for PostgreSQL (Neon or any other Postgres provider). The system is a **deterministic evidence pipeline first, ML second, LLM/agents last** — the LLM never invents facts or executes SQL directly; it reasons over structured evidence produced by collectors, statistical engines, and trained models.

Core stack: **Python + FastAPI** backend, **PostgreSQL/Neon** as both the target database and the telemetry/experiment store, **LightGBM** for all tabular ML, **LangGraph** for agent orchestration, **Next.js** dashboard frontend, **Docker-based shadow databases** for safe experimentation, **MLflow** for model tracking.

### User Connection Workflow

1. User signs up / logs into the dashboard.
2. User clicks **"Connect Database"** and supplies a Postgres connection string (host, port, db, user, password, SSL) — Neon, RDS, Supabase, or self-hosted Postgres all work the same way.
3. Backend performs a read-only test connection and checks required permissions/extensions.
4. Telemetry Collector begins polling read-only system views on a schedule.
5. Dashboard surfaces anomalies → Feature 1 diagnoses root cause → Feature 2 simulates a fix in a shadow DB → Feature 3 predicts/forecasts impact → user approves → change applied with canary + rollback → outcome logged and fed back into the training loop and priced (Feature 4).
6. The application's own metadata/experiment database can itself be hosted on Neon — this is separate from whatever database the user connects for monitoring.

---

## Feature 1 — Database Root Cause Diagnosis Engine

### Execution

Pipeline: `Postgres telemetry → deterministic evidence engine → ML anomaly detection → temporal/correlation engine → specialist agents → evidence graph → supervisor → causal diagnosis`.

A background collector polls Postgres system views continuously and writes normalized rows into an evidence store. A deterministic engine computes hard metrics (cardinality error, plan diffs, lock chains, vacuum lag) with no model involved. In parallel, an ML layer scores anomalies on a multivariate feature vector. A temporal correlator orders events into an evidence graph. Specialist LangGraph agents each analyze one domain and emit a hypothesis with confidence. A supervisor agent reconciles contradictions and produces a ranked root-cause report with a validation plan.

### Tech Stack

* **Frontend:** Next.js, React Flow for the evidence-graph timeline view.
* **Backend:** Python 3.12, FastAPI, asyncpg, SQLAlchemy, Pydantic; scheduled telemetry collector service.
* **AI/ML (all free, open-source, run locally):**
  * *Anomaly detection:* Isolation Forest (scikit-learn) as the sole anomaly-scoring model, over a ~17-feature multivariate vector (latency percentiles, exec/plan time, buffer hits/reads, temp I/O, lock wait, dead-tuple ratio, cache hit ratio, WAL rate, table growth, vacuum/analyze age). Robust Z-score used only as a lightweight interpretability layer alongside it, not as an alternative.
  * *Temporal model:* LSTM autoencoder (PyTorch) over 30–60 min windows for next-window anomaly probability. This is the one temporal model used — no separate TCN path is built.
  * *Root Cause Classifier:* LightGBM multi-label classifier over plan/telemetry features, predicting probabilities for classes such as `STALE_STATISTICS`, `PLAN_FLIP`, `CARDINALITY_MISESTIMATION`, `LOCK_CONTENTION`, `VACUUM_LAG`, `INDEX_MISSING`, `BUFFER_PRESSURE`, `IO_SATURATION`.
  * *Training data:* self-generated via a "Database Fault Laboratory" — Docker Postgres + pgbench workload generator + fault injector (stale stats, plan regression, skew, lock contention, vacuum starvation, index problems, I/O/buffer pressure) + ground-truth recorder. Walk-forward temporal split, no random shuffling.
* **Agents (LangGraph):**
  * *Planner Intelligence Agent* — plan regression, cardinality error, statistics freshness.
  * *Concurrency Agent* — blocking chains, lock waits, idle transactions.
  * *Vacuum Agent* — dead-tuple ratio, bloat, autovacuum backlog.
  * *I/O / Buffer Agent* — cache eviction, temp spill, WAL pressure.
  * *Schema / Index Agent* — missing/unused/redundant/wrong-order indexes.
  * *Supervisor Agent* — evidence weighting, contradiction resolution, causal ranking into primary/contributing/correlated/unrelated, produces the final root-cause report with a counterfactual validation plan.
* **Database / Postgres mechanisms:** `pg_stat_statements`, `pg_stat_activity`, `pg_stat_user_tables`, `pg_stat_user_indexes`, `pg_stats`, `pg_stat_progress_vacuum`, `pg_locks`, `pg_wait_events`, `EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON)`. Evidence store in PostgreSQL, historical archive in Parquet.
* **Tools/APIs:** OpenTelemetry for telemetry pipeline instrumentation.
* **Background jobs:** Scheduled polling job (every 1–5 min) per system view; async task queue triggers specialist agents.
* **Infrastructure:** Docker for the fault-injection lab.
* **Libraries:** NumPy, Pandas, Polars, scikit-learn, SciPy, `ruptures`, LightGBM, PyTorch, MLflow.

### Why These Technologies

Deterministic SQL/statistics computation grounds the diagnosis in real Postgres internals instead of LLM guesses. Isolation Forest and LightGBM are chosen as the single models for their respective jobs because the data is tabular, they train fast on hackathon-sized data, and they are fully free/local. LangGraph gives explicit, auditable agent-to-agent handoffs. Self-generated fault-injection data solves the "no public labeled dataset" problem.

---

## Feature 2 — Safe Simulation & Verification Sandbox

### Execution

Pipeline: `workload capture → deterministic candidate generation → HypoPG fast filter → ML impact prediction → shadow DB replay → statistical validation → adversarial (skeptic) review → policy engine → canary deployment → live verification → commit/rollback`.

Candidates (indexes, statistics changes, planner config, rewrites) are generated deterministically, cheaply pre-filtered with HypoPG, then scored by an ML impact-delta model. Top candidates are tested on a production-shaped shadow database by replaying captured production workload (paired baseline vs. candidate). Results go through statistical testing before a rule-based policy engine — not the LLM — decides whether to canary-deploy.

### Tech Stack

* **Frontend:** Next.js — experiment comparison view, skeptic-agent findings, canary live-monitoring panel.
* **Backend:** Python, FastAPI, asyncpg, SQLAlchemy; a single custom Replay Orchestrator built on asyncpg (this replaces `pgreplay` entirely — one replay engine, not two competing ones).
* **AI/ML (all free, open-source, run locally):**
  * *Query Performance Delta Predictor:* LightGBM regression over baseline vs. candidate plan + query fingerprint + workload + hardware features, predicting Δlatency, Δp95, ΔCPU, ΔI/O, Δbuffer-reads with an uncertainty estimate. This is the single model for this job — no separate plan-tree neural network is built for the MVP.
  * *Training data:* self-generated on the TPC-H benchmark database as the primary source (TPC-DS/TPC-C/JOB can be added later, not required for MVP). Includes deliberately bad optimizations (low-selectivity index, wrong column order, redundant index) so the model learns GOOD / BAD / NEUTRAL / REGRESSION.
  * *Multi-objective utility function:* a single deterministic weighted formula (not a model) combining latency/throughput gain against storage, write amplification, and regression risk.
* **Agents (LangGraph):**
  * *Experiment Agent* — creates shadow DB, installs candidate, runs replay, collects metrics.
  * *ML Scientist Agent* — interprets model prediction/confidence; triggers more experiments if confidence is low.
  * *Skeptic Agent* — adversarial: only searches for regressions (writes, storage, locks, parameter-sensitive edge cases), never approves.
  * *Verification Agent* — combines statistics + ML prediction + skeptic findings into VERIFIED / CONDITIONAL / REJECTED.
  * *Policy Agent* — hard, non-LLM-overridable rules (e.g. p95 improvement above threshold AND CI excludes zero AND regression rate below 2% → allow canary).
  * *Deployment Agent* — executes the approved change and manages canary/rollback.
* **Database / Postgres mechanisms:** `pg_stat_statements`, `auto_explain`, `pg_locks`, `pg_stat_activity`, `pg_statio_user_tables`, `pg_statio_user_indexes`, `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, **HypoPG** for hypothetical indexes, `CREATE INDEX CONCURRENTLY` for safe production application. Shadow database built with `pg_dump`/`pg_restore` full clone as the single, primary method (logical replication is a future enhancement, not part of the MVP path).
* **Tools/APIs:** `pgbench` for synthetic load generation (a separate purpose from the replay orchestrator — load generation vs. real-workload replay).
* **Background jobs:** Async job queue for shadow DB provisioning, replay execution, canary monitoring windows.
* **Infrastructure:** Docker containers for shadow databases (one per candidate + baseline).
* **Libraries:** HypoPG extension, LightGBM, SciPy (bootstrap, paired tests), NumPy, Pandas.

### Why These Technologies

HypoPG gives a near-zero-cost first filter before a real shadow experiment. A production-shaped shadow DB with paired replay converts a plan-cost claim into a measured, statistically validated result. A deterministic policy engine — not the LLM — makes the safety guarantee auditable.

---

## Feature 3 — Predictive ML + Closed-Loop Optimization

### Execution

Pipeline: `observe → forecast → generate candidate → simulate (via Feature 2) → measure actual outcome → learn prediction error → update model → select better strategy next time → (Feature 4) translate verified gain into $ ROI`. Feature 2's verified outcomes become the labeled training data here, closing the loop between prediction and reality.

### Tech Stack

* **Frontend:** Next.js — degradation-probability forecast timeline, predicted-vs-actual calibration chart, bandit performance view, MAE-over-iterations chart.
* **Backend:** Python, FastAPI, asyncpg; feature engineering pipeline turning raw telemetry into query/table/plan/workload/resource features.
* **AI/ML — four layers, all free/open-source:**
  * **L1 Workload Forecasting:** LightGBM regression with lag features, rolling means/std, growth rates, calendar features, plus conformal prediction for calibrated intervals. Predicts `degradation_probability(t)` rather than a raw metric.
  * **L2 Optimization Outcome Model:** LightGBM regression predicting expected latency/p95/I/O/CPU delta and success probability for a candidate, trained on Feature 2's verified experiment records. (Same model family as Feature 2's predictor — one LightGBM training pipeline reused, not a separate library.)
  * **L3 Strategy Selector:** Contextual Thompson Sampling bandit over actions {index, partial index, rewrite, statistics update, vacuum/analyze, config change, do nothing}, reward = latency/IO/CPU improvement − risk penalty − implementation cost. Rolled out in phases: rule-based → supervised prediction → bandit → offline policy evaluation (Inverse Propensity Scoring) before it influences live recommendations.
  * **L4 Learning & Calibration:** MLflow-tracked retraining loop comparing predicted vs. actual outcome, tracking MAE/RMSE/coverage over iterations; drift detection via Evidently to flag when workload shape has changed.
  * *Training data volume:* target 300+ verified experiments from the Feature 2 lab; temporal/walk-forward train-test split only.
* **Agents (LangGraph, minimal by design):**
  * *Forecasting/Planning Agent* — reads ML predictions, decides if degradation risk crosses a threshold, requests a Feature 2 simulation, chooses next action.
  * *Learning Agent* — collects experiment outcomes, validates labels, triggers retraining, evaluates and promotes new model versions.
* **Database / Postgres mechanisms:** same telemetry views as Features 1/2, materialized to Parquet and queried via DuckDB for training speed.
* **Tools/APIs:** MLflow for experiment tracking and model registry. (Feast feature store intentionally excluded — adds complexity with no requirement for the MVP.)
* **Background jobs:** Scheduled retraining job; async job logs each Feature 2 outcome as a labeled training row.
* **Infrastructure:** Same Docker-based workload lab as Feature 1/2, reused.
* **Libraries:** LightGBM, NumPy, Pandas, Polars, scikit-learn, DuckDB, MLflow, Evidently.

### Why These Technologies

LightGBM is used as the single model family across L1 and L2 rather than mixing multiple gradient-boosting libraries — this keeps the training/serving pipeline simple and consistent. Contextual bandits let the system learn which optimization type works for which workload context. Routing every prediction through Feature 2 for real measurement is what makes the "self-improving" claim measurable rather than asserted.

---

## Feature 4 — Cost-to-Dollar ROI Translation

### Execution

A deterministic (non-ML, non-LLM) mapping layer that converts Feature 2's measured deltas (CPU, I/O, storage, latency, buffer reduction) and workload frequency into an estimated dollar cost/savings figure, using a cloud provider pricing lookup table.

### Tech Stack

* **Backend:** Python, FastAPI — pure calculation service, no model involved.
* **Tools/APIs:** A single static pricing reference table (compute-hour, storage-GB, IOPS) chosen from one cloud provider for consistency, rather than multiple pricing sources.
* **Database:** Reads verified experiment outcomes from the same experiment store used by Features 2/3.
* **Frontend:** Next.js — "$ saved / month" card attached to each verified optimization.

### Why These Technologies

The dollar figure must be traceable to real measured deltas, not an LLM estimate — keeping this fully deterministic avoids fabricated ROI numbers and keeps the number auditable back to the underlying experiment.

---

## Final Consolidated Stack

| Layer | Technology (single choice) | Used In |
|---|---|---|
| Frontend | Next.js (React), React Flow for graphs | All features |
| Backend API | Python 3.12, FastAPI, Pydantic | All features |
| DB access | asyncpg, SQLAlchemy | All features |
| Target DB | PostgreSQL (Neon or any provider) | All features |
| Postgres introspection | `pg_stat_statements`, `pg_stat_activity`, `pg_stat_user_tables/indexes`, `pg_stats`, `pg_stat_progress_vacuum`, `pg_locks`, `pg_wait_events`, `auto_explain`, `EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON)` | Feature 1, 2, 3 |
| Safe experimentation | HypoPG, shadow DB via `pg_dump`/`pg_restore`, `CREATE INDEX CONCURRENTLY` | Feature 2 |
| Load/replay | pgbench (load generation), custom asyncpg Replay Orchestrator (real replay) | Feature 2, 3 |
| Anomaly detection | Isolation Forest (scikit-learn) | Feature 1 |
| Tabular ML | LightGBM (single library used everywhere) | Feature 1, 2, 3 |
| Temporal model | LSTM autoencoder (PyTorch) | Feature 1 |
| Bandit / decision learning | Contextual Thompson Sampling, Inverse Propensity Scoring | Feature 3 |
| Experiment tracking | MLflow | Feature 1, 2, 3 |
| Drift monitoring | Evidently | Feature 3 |
| Agent orchestration | LangGraph | Feature 1, 2, 3 |
| Analytical storage | DuckDB + Parquet | Feature 1, 3 |
| Fault/data generation | Docker, TPC-H benchmark, custom fault injector | Feature 1, 2, 3 |
| Background jobs | Async scheduled workers | All features |
| Infra | Docker (shadow DBs, fault lab), standard container deploy for API/services | All features |
| Core ML libs | NumPy, Pandas, Polars, scikit-learn, SciPy | Feature 1, 2, 3 |

All models above are free and open-source — no paid model API is used anywhere in the ML pipeline.
