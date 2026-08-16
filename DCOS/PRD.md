
# Product Requirements Document

## 1. Product Overview

**Product name:** TBD (referred to throughout as "the AI DBA" / "the system")

**Problem:** PostgreSQL databases degrade silently — stale statistics, plan flips, lock contention, vacuum lag, missing/unused indexes, and I/O pressure accumulate over time. Traditional monitoring tools surface symptoms (slow query, high CPU) but not causal evidence. Existing "AI wrapper" tools feed raw metrics into an LLM and ask it to explain the problem, which produces plausible-sounding but unverified guesses. DBAs are expensive, and most engineering teams do not have one on staff.

**Vision:** Build a database intelligence system that behaves like a rigorous DBA, not a chatbot: it collects deterministic evidence from PostgreSQL internals, uses ML models to detect and predict problems, uses specialized agents to build a causal diagnosis, safely simulates and statistically verifies any proposed fix before it touches production, and learns from every real outcome to improve future predictions.

**Target users:** TBD — inferred from documents to be engineering teams / backend developers who own a PostgreSQL database (via Neon, RDS, Supabase, self-hosted, etc.) and do not have a dedicated DBA.

**Value proposition:**
- Root-cause diagnosis backed by deterministic evidence (query plans, statistics, locks, vacuum state), not LLM speculation.
- No unvalidated changes to production — every optimization is simulated, statistically verified, and (where required) approved by a human before execution.
- The system gets measurably better over time via a closed feedback loop between predicted and actual optimization outcomes.

## 2. Goals & Non-Goals

**Goals**
- Continuously monitor a user's PostgreSQL database using read-only telemetry collection.
- Detect anomalies and performance regressions using deterministic evidence plus ML anomaly detection.
- Produce causal, evidence-backed root-cause diagnoses via a multi-agent architecture with a supervisor/reconciliation layer.
- Generate optimization candidates (indexes, statistics changes, planner/config changes, query rewrites) deterministically — not via free-form LLM SQL generation.
- Simulate and statistically verify candidates (HypoPG, shadow database replay, paired statistical testing) before any production change.
- Require human approval for any action that modifies the production database.
- Execute approved changes via a guarded canary deployment with automatic rollback.
- Feed every real outcome back into the ML layer to reduce prediction error over time (closed-loop learning).
- Forecast future degradation (not just react to current problems) where the predictive ML layer (Feature 3) is in scope.

**Non-Goals**
- The system does not autonomously execute schema/DDL changes on production without approval (this is explicitly out of scope per the safety architecture in the source material).
- The system does not fine-tune or train a foundation LLM. LLMs are used as a reasoning/orchestration layer over deterministic evidence, not as the source of truth.
- The system does not claim wall-clock performance guarantees from HypoPG estimates alone — HypoPG output is a planner-cost signal, not a verified performance number.
- The system does not manage non-PostgreSQL databases (MySQL, MongoDB, etc.) — TBD if multi-engine support is ever in scope; not supported by the source documents.
- Feature 4 (Cost-to-Dollar ROI) mapping logic (the exact $ conversion formula) is not fully specified in the source material — treated as TBD below.

## 3. User Personas

| Persona | Description | Needs |
|---|---|---|
| Backend/Platform Engineer | Owns a production PostgreSQL database, no dedicated DBA on team | Fast, trustworthy root-cause diagnosis; confidence that recommended fixes won't cause outages |
| Engineering Lead / CTO | Cares about reliability and cost | Audit trail of what changed and why; measurable performance/cost improvement over time |
| (Future) DBA / SRE | Power user validating agent recommendations | Full evidence graph, statistical verification detail, manual override/approval controls |

TBD: exact target company size, industry, and whether this is aimed at self-serve SaaS users or enterprise teams — not specified in source documents.

## 4. Core User Journey

```
User → Sign up / Log in
     → Connect PostgreSQL database (connection string; ideally a dedicated
       read-only monitoring role)
     → System tests connection (reachability, credentials, required
       permissions/extensions e.g. pg_stat_statements)
     → System begins continuous read-only telemetry collection
     → Deterministic evidence engine + ML anomaly detection run continuously
     → Problem detected (e.g. query regression, plan flip, vacuum lag)
     → Specialist agents investigate in their domain (planner, concurrency,
       vacuum, I/O/buffer, schema/index)
     → Supervisor agent reconciles evidence, resolves contradictions,
       produces ranked root-cause diagnosis with confidence scores
     → Candidate optimization(s) generated deterministically (not free-form
       LLM SQL)
     → HypoPG fast filter narrows candidates
     → ML Impact Predictor estimates latency/CPU/IO/storage deltas with
       confidence intervals
     → Shadow database simulation + paired statistical verification
       (bootstrap CI, effect size, regression-rate check)
     → Skeptic/Regression Hunter agent adversarially searches for harm
     → Policy engine applies hard rules (independent of LLM judgment)
     → User is shown the diagnosis, the proposed fix, and the verified
       simulated impact
     → User approval requested for any production-modifying action
     → Approved action executed via guarded canary deployment
     → Live verification compares before/after in production
     → COMMIT (success) or automatic ROLLBACK (regression detected)
     → Actual outcome is recorded and compared to the original prediction
     → Closed-loop learner updates model error metrics; models/bandit
       policy retrained and promoted if they improve
     → Future diagnoses and predictions become more accurate
```

Two databases are involved and must be kept conceptually distinct throughout the product:
- **Monitored database** — the user's own PostgreSQL instance (Neon, RDS, Supabase, self-hosted, etc.). Accessed read-only except for approved, guarded optimization execution.
- **Application database** — the system's own PostgreSQL store for telemetry history, evidence graphs, experiments, ML training data, accounts, approvals, and audit logs.

## 5. Feature Requirements

### Feature 1 — Root Cause Diagnosis Pipeline (Evidence-Driven Investigation)

**Problem solved:** Generic "AI explains your slow query" tools produce unverified guesses. Teams need a diagnosis backed by concrete PostgreSQL evidence and a defensible causal chain.

**User experience:** Dashboard surfaces a detected problem (e.g. "Query regression detected"), then a root-cause report showing primary cause, contributing causes, confidence percentages, supporting evidence, and a timeline of what happened first.

**Functional requirements**
- Continuous collection of PostgreSQL telemetry (see Database Architecture, §8).
- Deterministic evidence computation (plan diffing, cardinality error, lock graph construction, vacuum/bloat metrics) independent of any ML/LLM component.
- ML-based multivariate anomaly detection over a feature vector (latency percentiles, execution/plan time, rows, buffer stats, temp I/O, lock waits, dead-tuple ratio, cache hit ratio, WAL rate, growth rates, vacuum/analyze age).
- Temporal correlation engine that orders events ("what changed first / next / co-moved") to build causal hypotheses rather than isolated alerts.
- Plan Fingerprinting: normalize every query execution into `query_hash`, `plan_hash`, operator tree, join order, scan types, index usage, estimated/actual rows, buffer stats, execution time — used to detect `PLAN_FLIP` events.
- Multi-label root-cause classification (a database can have multiple simultaneous causes, e.g. `STALE_STATISTICS` + `VACUUM_LAG` + `PLAN_FLIP`), followed by a separate causal-ranking step (`PRIMARY` / `CONTRIBUTING` / `CORRELATED` / `UNRELATED`).
- Evidence Graph construction showing the causal chain (e.g. bulk load → stale stats → cardinality error → plan flip → latency increase).

**Inputs:** Live PostgreSQL telemetry (see §8), historical telemetry from the application database, current plan/statistics snapshots.

**Outputs:** Root Cause Report — primary cause + confidence, contributing causes, evidence list, timeline, recommended action, validation plan.

**AI/ML requirements:** See §7 (Model Hierarchy — anomaly detection, root-cause classifier). No claim of foundation-model training; classifiers/anomaly models are trained by the product team on generated experiment data (see §7 and §9-adjacent Fault Laboratory).

**Agent workflow:** See §6 (Agentic Architecture) — Planner Intelligence Agent, Concurrency Agent, Vacuum Agent, I/O/Buffer Agent, Schema/Index Agent → Supervisor Agent with contradiction-reconciliation protocol.

**Tools/APIs:** Read-only PostgreSQL introspection functions per agent (see §6, agent tool lists), `EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON)`.

**Database interactions:** Read-only against the monitored database. Read/write against the application database (telemetry storage, evidence graphs, diagnosis history).

**Safety requirements:** Diagnosis is purely observational — no writes to the monitored database occur in this feature. All agent tool access is scoped to read-only introspection tools per §14.

**Failure cases:** Insufficient telemetry history (cold start) → diagnosis confidence should be explicitly lowered/flagged, not hidden. Contradictory agent evidence → resolved via the Supervisor's reconciliation protocol (earliest-explaining hypothesis wins, evidence directness weighted over correlation); if unresolved, root cause is reported as `UNKNOWN` with all hypotheses shown rather than a forced pick.

**Acceptance criteria**
- Given a query regression caused by a known injected fault (from the Fault Laboratory, §7), the system produces a root-cause report whose `primary_root_cause` matches the injected fault's ground-truth label at a rate defined in §21 (Success Metrics).
- Every claim in the root-cause report is traceable to a specific evidence item (metric, plan diff, or timeline event) — no unsupported LLM narrative is presented as evidence.
- Diagnosis is generated without any write operation against the monitored database.

---

### Feature 2 — Safe Simulation & Verification Sandbox

**Problem solved:** Recommending `CREATE INDEX` (or any change) without verifying real-world impact risks production outages. Planner cost estimates (e.g. from HypoPG) are not proof of real performance.

**User experience:** User sees a candidate optimization along with a verified simulation report: baseline vs. candidate latency/p95/p99, bootstrap confidence interval, statistical significance, regression rate, and an explicit `VERIFIED` / `CONDITIONAL` / `REJECTED` verdict — before being asked to approve anything.

**Functional requirements**
- Deterministic Candidate Generation: index (single-column, composite, partial, covering, expression), statistics changes (ANALYZE, statistics target, extended statistics), planner/config changes, query rewrite candidates. The LLM does not invent arbitrary SQL changes.
- HypoPG fast filter: create hypothetical indexes and compare planner cost estimates to reduce e.g. 100 candidates → top 10, without consuming real disk/CPU. Explicitly communicated to the user as a planner-cost signal, not a proven performance result.
- ML Impact Predictor: predicts latency/p95/CPU/IO/write-amplification deltas with uncertainty (confidence interval), trained on structured plan + query + workload features (see §7).
- Shadow Database Laboratory: production-shaped PostgreSQL copy (full clone via `pg_dump`/`pg_restore`, logical-replication-based replica, or a sampled clone for fast demos — mode is configurable) hosting a baseline and one or more candidates.
- Workload Replay: replay captured production SQL (query, parameters, timestamp, transaction boundary) against baseline and candidate shadows with controlled concurrency, ordering, and parameter-distribution sampling (not just the most common parameter value — rare/medium-frequency values must also be tested to catch parameter-sensitive plan regressions).
- Paired Statistical Verification: per-query paired latency deltas, bootstrap confidence interval, p95/p99 comparison, paired significance test, effect size, and a regression-rate check (% of queries that got worse), not just an average improvement.
- Skeptic / Regression Hunter Agent: adversarial agent whose sole mandate is to find evidence the candidate is unsafe (write amplification, bloat, storage growth, cache pressure, lock contention, planner instability, low-selectivity workloads, parameter sensitivity).
- Policy Engine: hard, deterministic rules (e.g. p95 improvement > threshold AND CI excludes zero AND regression_rate < threshold AND write-latency increase < threshold AND storage increase < threshold AND skeptic score < threshold) that gate progression to canary. The LLM cannot override the policy engine's verdict.
- Canary Deployment: guarded rollout to production (e.g. `CREATE INDEX CONCURRENTLY` for index changes) with a live monitoring window (e.g. 15 minutes) tracking p50/p95/p99, error rate, lock waits, CPU, IO, throughput, write latency.
- Automatic Rollback: triggered by hard thresholds (e.g. p95 regression > 15%, error rate > 1%, lock timeout > 2× baseline, write latency > 20%).

**Inputs:** Candidate optimization from Feature 1 diagnosis or Feature 3 forecasting; production workload capture; monitored-database schema/statistics snapshot.

**Outputs:** Simulation/verification report (statistical + ML), Skeptic findings, Policy Engine verdict, canary result (COMMIT/ROLLBACK), full experiment record for the ML training dataset.

**AI/ML requirements:** Query Performance Delta Predictor (LightGBM/XGBoost primary; optional plan-tree neural encoder + tabular fusion as a stretch model) — see §7. Trained on self-generated experiment data (positive, negative, and neutral/regression examples), not a public dataset.

**Agent workflow:** Experiment Agent (mechanical: create shadow, install candidate, run replay, collect metrics) → ML Scientist Agent (interprets prediction/confidence, can request more experiments if confidence is low) → Skeptic Agent (adversarial) → Verification Agent (produces VERIFIED/CONDITIONAL/REJECTED) → Policy Agent (deterministic gate) → Deployment Agent (canary execution). Orchestrated via a supervisor (recommend LangGraph or equivalent graph-based orchestration — see §6).

**Tools/APIs:** HypoPG functions, shadow-DB provisioning tools, replay orchestrator (custom, built around `asyncpg` rather than relying solely on `pgreplay`), statistical testing library, canary metrics collectors.

**Database interactions:** Read-only + HypoPG hypothetical objects (no real storage cost) against monitored DB during simulation; full read/write against the isolated Shadow DB; guarded read/write (DDL/config only, never arbitrary data mutation) against monitored DB only after approval + policy pass, during canary.

**Safety requirements:**
- No LLM-generated SQL is ever executed directly against the monitored production database.
- All production-modifying actions flow: LLM/agent proposal → structured action → policy engine → (if required) human approval → guarded execution tool → PostgreSQL.
- Index creation on production uses `CONCURRENTLY` where applicable to avoid blocking.
- Any canary threshold breach triggers automatic rollback without requiring further human input.

**Failure cases:** Shadow DB provisioning failure → optimization is not simulated, and no recommendation is surfaced as "verified" (falls back to a lower-confidence, HypoPG-only estimate, clearly labeled as such). Statistical test underpowered (too few paired samples) → verdict downgraded to `CONDITIONAL` rather than `VERIFIED`. Canary rollback → experiment recorded as `success: false` for the training dataset (§7, §9).

**Acceptance criteria**
- No optimization reaches the "ready for approval" state without passing through HypoPG filter, ML prediction, shadow simulation, statistical verification, Skeptic review, and Policy Engine — in that order.
- Every production DDL/config execution has a corresponding, retrievable audit record (who/what/when/policy result/rollback status).
- A canary that breaches a defined threshold is automatically rolled back within the monitoring window without human intervention.

---

### Feature 3 — Predictive ML & Closed-Loop Optimization

**Problem solved:** Reactive optimization (fix after it breaks) is weaker than predicting degradation before it happens, and a system that never learns from its own mistakes never improves.

**User experience:** Dashboard shows forecasted degradation probability over time (e.g. "61% probability of index-effectiveness degradation within 5 days"), proactively suggested optimizations before failure, and a visible model-improvement curve (prediction error decreasing over iterations) as evidence the system is learning.

**Functional requirements**
- **L1 — Workload Forecasting Model:** predicts workload/resource degradation using lag and rolling-window features (1h–168h), growth rates, time-of-day/day-of-week, table/index size, query frequency, latency percentiles, buffer reads, CPU time. Quantile regression + conformal calibration for prediction intervals rather than a single point estimate. Forecast target includes a `degradation_probability(t)` curve, not just a raw metric projection.
- **L2 — Optimization Outcome Model:** predicts expected latency/p95/IO/CPU deltas and a success probability for a *specific* candidate optimization in a *specific* workload context, with an explicit uncertainty range. Low-confidence predictions (wide interval) must trigger mandatory simulation (Feature 2) rather than direct recommendation.
- **L3 — Strategy Selector (Contextual Bandit):** learns, per workload context, which optimization type (index / partial index / rewrite / statistics / vacuum / config / do-nothing) historically performs best, using Contextual Thompson Sampling. Reward function combines latency/IO/CPU improvement minus risk penalty minus implementation cost. Must be gated behind a rollout sequence: (1) rule-based exploration → (2) supervised prediction only → (3) contextual bandit → (4) offline policy evaluation (IPS / doubly robust estimation) before the bandit is allowed to influence live recommendations.
- **L4 — Learning & Calibration:** every simulated/executed experiment (from Feature 2) becomes a labeled training record. Track prediction error (MAE/RMSE) over iterations as the core "system is improving" metric. Track calibration (does 90%-confidence actually cover ~90% of outcomes). Track feature/prediction/error drift and flag when retraining is recommended.
- Forecast/Planning Agent: observes ML predictions, decides if degradation risk crosses a threshold, requests simulation from Feature 2, compares predicted vs. simulated result, chooses next action.
- Learning Agent: collects experiment outcomes, validates labels, triggers retraining, evaluates new model versions, promotes a new model only if it measurably improves over the current one.
- Train/test splitting must be temporal (walk-forward validation) — never a random split — to avoid time-series leakage.

**Inputs:** Continuous telemetry (query/table/plan metrics), historical Feature 2 experiment outcomes, current forecast state.

**Outputs:** Degradation forecasts with confidence intervals, ranked optimization candidates with predicted impact + uncertainty, bandit-selected strategy recommendation, model performance/calibration/drift reports.

**AI/ML requirements:** LightGBM (primary) for forecasting and outcome prediction; Contextual Thompson Sampling for strategy selection; conformal prediction for calibrated intervals; MLflow for experiment tracking, model versioning, and promotion decisions. No foundation-model fine-tuning — this is a self-trained tabular/time-series ML system.

**Agent workflow:**
```
Telemetry → Feature extraction → Forecast
  → Risk > threshold? → NO: continue monitoring
                       → YES: generate candidates → bandit ranks strategies
                         → outcome model predicts impact
                         → confidence check → Feature 2 simulation
                         → actual measurement → prediction-vs-actual stored
                         → retrain → evaluate new model → promote if better
```

**Tools/APIs:** Feature engineering pipeline, MLflow tracking API, (optional, non-mandatory for MVP) Feast feature store or direct PostgreSQL/DuckDB feature queries.

**Database interactions:** Read-only against monitored DB for feature extraction; read/write against application DB for experiment/prediction/bandit-event storage (see §13 Data Model); Feature 2's Shadow DB used for verification, not this feature directly.

**Safety requirements:** The bandit may only *rank/suggest*; it never directly triggers production execution — every suggestion still flows through Feature 2's simulation → policy → approval pipeline. Rollout gating (rule-based → supervised → bandit → offline-evaluated) is mandatory before bandit output influences live recommendations.

**Failure cases:** Insufficient experiment volume (cold start, <300–500 experiments per source guidance) → outcome-model predictions flagged as low-confidence / not used for autonomous ranking, system falls back to rule-based candidate ordering. Workload drift detected → confidence reduced, retraining recommended, not silently applied.

**Acceptance criteria**
- Prediction error (MAE) on the outcome model is tracked per model version and is non-increasing across promoted versions (or the new version is not promoted).
- Calibration report is available showing predicted-confidence vs. actual-coverage across at least 5 confidence buckets.
- Bandit-influenced recommendations only appear after the model has passed offline policy evaluation — not before.

---

### Feature 4 — Cost-to-Dollar ROI Translation

**Problem solved:** Technical improvement numbers (latency %, IO %) don't communicate business value to non-technical stakeholders.

**User experience:** Alongside a completed optimization, the user sees a deterministic estimate of dollar impact (e.g. reduced compute/IO cost) rather than an LLM-generated dollar figure.

**Functional requirements**
- Deterministic mapping from Feature 2's measured deltas (CPU reduction, I/O reduction, storage change, latency reduction, buffer reduction, workload frequency) to a cost estimate. **The exact mapping formula and pricing inputs (e.g. cloud provider cost-per-unit assumptions) are not specified in the source documents — marked TBD.**
- Must be explicitly deterministic/rule-based, not LLM-generated, consistent with the rest of the system's "LLM is not the source of truth" principle.

**Inputs:** Verified, measured (not predicted) deltas from Feature 2 canary/commit results; TBD pricing/cost model inputs.

**Outputs:** Dollar-denominated ROI estimate attached to each completed optimization.

**AI/ML requirements:** None — deterministic calculation only.

**Agent workflow:** N/A — this is a calculation service, not an agentic feature.

**Tools/APIs:** TBD (would likely require cloud-provider pricing API or user-supplied cost assumptions).

**Database interactions:** Read-only against application DB (experiment outcome records).

**Safety requirements:** N/A (no production DB interaction).

**Failure cases:** Missing pricing input → ROI section omitted/marked "cost model not configured" rather than fabricated.

**Acceptance criteria:** TBD pending resolution of the pricing/cost model. At minimum, ROI is only calculated from *measured* (post-canary) deltas, never predicted deltas.

## 6. Agentic Architecture

**Agent hierarchy**

```
                         Supervisor Agent
        (evidence weighting, contradiction resolution, causal ranking)
                                │
        ┌───────────┬──────────┼──────────┬───────────────┐
        ▼           ▼          ▼          ▼               ▼
   Planner      Concurrency  Vacuum    I/O/Buffer     Schema/Index
   Intelligence  Agent        Agent     Agent           Agent
   Agent

Feature 2 orchestration (parallel sub-graph):
                         Supervisor
                                │
       ┌────────────────┬──────┴───────┬────────────────┐
       ▼                ▼               ▼                ▼
  Experiment Agent  ML Scientist    Skeptic Agent   Verification Agent
                       Agent                                │
                                                              ▼
                                                       Policy Agent
                                                              │
                                                              ▼
                                                     Deployment Agent

Feature 3 orchestration:
   Forecast/Planning Agent  ──requests simulation from──▶  Feature 2 graph
   Learning Agent (retrain / evaluate / promote models)
```

**Specialized agents and scoped tools** (each agent is restricted to its own domain's read-only tools — no agent has blanket database access):
- **Planner Intelligence Agent** — `get_explain_plan`, `get_plan_history`, `get_pg_stats`, `get_table_statistics`, `compare_plan`, `calculate_cardinality_error`.
- **Concurrency Agent** — `get_pg_activity`, `get_pg_locks`, `get_wait_events`, `build_lock_graph`.
- **Vacuum Agent** — `get_table_stats`, `get_vacuum_progress`, `get_autovacuum_history`, `estimate_bloat`, `get_dead_tuple_ratio`.
- **I/O / Buffer Agent** — `get_buffer_stats`, `get_io_stats`, `get_explain_buffers`, `get_temp_file_stats`, `get_wal_stats`.
- **Schema / Index Agent** — `get_indexes`, `get_index_usage`, `get_table_schema`, `get_constraints`, `get_query_plan`.
- **Experiment Agent** (Feature 2) — shadow provisioning, candidate installation, replay execution, metric collection (mechanical, minimal LLM reasoning).
- **ML Scientist Agent** (Feature 2) — interprets outcome-model predictions/confidence/feature importance; can request additional experiments.
- **Skeptic Agent** (Feature 2) — adversarial; sole objective is to find evidence of harm.
- **Verification Agent** (Feature 2) — produces VERIFIED / CONDITIONAL / REJECTED.
- **Policy Agent** (Feature 2) — deterministic rule evaluation; not an LLM decision point, cannot be overridden by upstream agent output.
- **Deployment Agent** (Feature 2) — executes approved, policy-passed changes via canary.
- **Forecast/Planning Agent** (Feature 3) — decides when predicted risk warrants requesting simulation.
- **Learning Agent** (Feature 3) — manages the closed feedback loop and model promotion.

**Tool calling:** Every agent tool is read-only introspection except the Deployment Agent's guarded execution tools, which require: (a) Policy Agent pass, and (b) human approval for any production-modifying action (per §9).

**Memory:** Agents operate over the Evidence Graph and Temporal Correlator output for the current investigation (short-term/session memory), plus historical experiment/diagnosis records in the application database (long-term memory) for pattern reuse across investigations.

**Planning:** Supervisor-level planning decides which specialist agents to invoke based on the anomaly signature; Feature 2's Experiment Agent plans shadow/replay execution; Feature 3's Forecast/Planning Agent plans when to trigger simulation.

**Reasoning:** LLM reasoning is used to interpret and reconcile structured agent outputs (evidence weighting, contradiction resolution) — never to author raw SQL or bypass the deterministic evidence/policy layers.

**Verification:** Counterfactual validation for diagnoses (e.g., re-run ANALYZE + EXPLAIN in a sandbox and confirm the plan/estimate actually improves before raising confidence) and full statistical verification for optimizations (Feature 2, §5/§9).

**Human-in-the-loop:** Required before any production-modifying action executes (DDL, config change, or query rewrite deployment). Diagnosis, forecasting, simulation, and recommendation generation are autonomous; execution is not.

**Retry/fallback behavior:** Low-confidence ML predictions trigger additional simulation rather than a direct recommendation. Contradictory specialist-agent evidence triggers the Supervisor's reconciliation protocol rather than an arbitrary tie-break. Shadow-DB provisioning failure falls back to a clearly-labeled lower-confidence (HypoPG-only) estimate instead of silently upgrading confidence.

## 7. AI/ML Architecture

**Models used (self-trained on generated experiment data; not foundation-model fine-tuning):**

| Model | Purpose | Approach |
|---|---|---|
| Multivariate anomaly detector | Detect abnormal telemetry state | Isolation Forest + robust covariance/z-score + change-point detection (e.g. `ruptures`) |
| Temporal anomaly model (optional/advanced) | Predict near-term anomaly probability from recent telemetry window | LSTM autoencoder (baseline) or TCN / Transformer (stretch) |
| Root-Cause Classifier | Multi-label causal classification (STALE_STATISTICS, PLAN_FLIP, CARDINALITY_MISESTIMATION, LOCK_CONTENTION, INDEX_MISSING, INDEX_UNUSED, VACUUM_LAG, BLOAT, BUFFER_PRESSURE, IO_SATURATION, TEMP_SPILL, CONNECTION_CONTENTION, CHECKPOINT_PRESSURE, UNKNOWN) | Multi-label classifier (gradient-boosted trees) + separate causal-ranking layer |
| Query Performance Delta Predictor (Feature 2) | Predict latency/p95/CPU/IO/write-amplification deltas for a candidate optimization, with uncertainty | LightGBM/XGBoost (primary); optional plan-tree neural encoder + tabular fusion ensemble (stretch) |
| L1 Workload Forecasting Model (Feature 3) | Forecast workload/resource degradation, degradation probability curve | LightGBM + lag/rolling features + conformal prediction (quantile regression for P50/P90/P95) |
| L2 Optimization Outcome Model (Feature 3) | Predict whether/how much a candidate will help, with success probability | LightGBM/CatBoost regression + uncertainty head |
| L3 Strategy Selector (Feature 3) | Learn which optimization type works best per workload context | Contextual Thompson Sampling (contextual bandit); rollout gated behind rule-based → supervised → bandit → offline-evaluated phases |
| L4 Learning & Calibration (Feature 3) | Track whether the system is actually improving | MLflow + calibration tracking + drift detection |

**Training/fine-tuning requirements:** All models above are trained by the product team on a self-generated dataset (see Database Fault Laboratory / Database Optimization Laboratory below) — the source documents explicitly reject relying on public/Kaggle datasets. No LLM fine-tuning occurs; LLM usage is limited to reasoning/orchestration over structured model and evidence output.

**Feature engineering:** Query fingerprints (tables, predicates, joins, operators, estimated/actual rows, latency percentiles, frequency), table features (row counts, dead/live tuples, scan ratios, growth rates), plan features (node types, cost, buffer hits/reads, cardinality error = `log(actual_rows+1) - log(estimated_rows+1)`), workload features (QPS, distribution), and, for the outcome model, candidate-optimization features (type, columns, selectivity, partial predicate, statistics target).

**Anomaly detection:** Multivariate feature vector over latency percentiles, execution/plan time, rows, buffer hit/read, temp read/write, lock wait, active sessions, dead-tuple ratio, cache-hit ratio, WAL rate, table growth, autovacuum/analyze age. See model table above.

**Prediction:** Degradation forecasting (L1) and optimization outcome prediction (L2), both with calibrated uncertainty intervals rather than point estimates.

**Ranking/recommendation:** Contextual bandit (L3) ranks candidate strategies per workload context; utility function combines performance/CPU/IO improvement minus storage cost, write amplification, and regression risk (multi-objective, not latency-only).

**Feedback loop:** Every Feature 2 experiment (predicted vs. actual outcome) becomes a labeled training record stored in the application database; used to retrain L1/L2/root-cause classifier and update the L3 bandit's policy.

**Evaluation metrics:**
- Forecasting: MAE, RMSE, MAPE, prediction-interval coverage.
- Optimization outcome model: MAE, RMSE, R², Spearman rank correlation, calibration.
- Bandit: cumulative reward, regret, policy improvement, success rate; evaluated offline first via IPS/doubly-robust estimation before live deployment.
- Root-cause classifier: precision/recall/F1 per class against ground-truth injected faults (see §21).

**Model serving:** TBD — source documents do not specify a serving framework (e.g. batch scoring vs. real-time inference service). Recommend a lightweight internal scoring service given the tabular/tree-based model choice; not confirmed by source material.

**Retraining strategy:** Triggered by (a) sufficient new labeled experiment volume, (b) detected feature/prediction/error drift, or (c) scheduled interval (TBD cadence). New model versions are evaluated against the currently-promoted version and only promoted if they show measurable improvement (tracked in MLflow).

**Training data generation (both a Database Fault Laboratory for Feature 1's classifier and a Database Optimization Laboratory for Feature 2/3's predictors):**
- Dockerized PostgreSQL + workload generator (pgbench, TPC-H, TPC-DS, TPC-C/HammerDB, JOB) + fault injector + telemetry collector + ground-truth recorder.
- Fault injection matrix: stale statistics, plan regression, cardinality misestimation, lock contention, vacuum starvation, index problems (missing/unused/low-selectivity/wrong composite), I/O pressure, buffer pressure — each with a recorded ground-truth label.
- Optimization experiment generation includes both positive (genuinely helpful) and negative (bad/regression-causing) candidates so the outcome model learns to distinguish GOOD/BAD/NEUTRAL/REGRESSION, not just "good" examples.
- Temporal train/test split (walk-forward validation) — never random — to prevent time-series leakage.
- Target volumes referenced in source material (proposed, not guaranteed): minimum ~300–500 verified experiments, good ~1,000–5,000, excellent 10,000+; diversity prioritized over raw volume.

## 8. Database Architecture

Two distinct PostgreSQL roles must never be conflated:

**A. Monitored Database (user's own PostgreSQL — Neon, RDS, Supabase, self-hosted, etc.)**
- Accessed via read-only role for telemetry/monitoring; guarded read/write only for approved, policy-passed optimization execution.
- Required extension: `pg_stat_statements` (must be enabled; role needs sufficient privilege, e.g. `pg_read_all_stats` or superuser depending on PostgreSQL version, to read it).
- Telemetry sources collected continuously:
  - **Query-level:** `pg_stat_statements` (queryid, calls, total/mean/min/max exec time, rows, shared/temp blocks hit/read/dirtied/written, WAL bytes, plans, plan time).
  - **Activity/locking:** `pg_stat_activity`, `pg_locks`, wait events (pid, query, state, wait_event_type/wait_event, backend_xid/xmin, query_start, xact_start, blocking_pid, lock mode, relation).
  - **Table/statistics intelligence:** `pg_stat_user_tables`, `pg_stat_user_indexes`, `pg_stats`, `pg_class`, `pg_index`, `pg_attribute` (n_live_tup, n_dead_tup, seq_scan, idx_scan, last_(auto)analyze/(auto)vacuum, vacuum/analyze counts; n_distinct, most_common_vals/freqs, histogram_bounds, correlation, null_frac).
  - **Vacuum/bloat:** `pg_stat_progress_vacuum`, computed dead_tuple_ratio, vacuum_age, analyze_age, autovacuum_lag, table/index growth rate, estimated bloat.
  - **Execution plans:** `EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON)`, parsed into structured plan features (never fed raw JSON to the LLM).
  - **I/O statistics:** `pg_statio_user_tables`, `pg_statio_user_indexes`.
  - Optional: `auto_explain` for automatic slow-query plan capture.
- Query plans/JSON are parsed into structured features (node type, estimated/actual rows, estimate error ratio, time, loops, shared hit/read, temp read/written) — raw JSON is never passed directly into the LLM reasoning layer.

**B. Application Database (system's own store)**
- Hosts telemetry history, evidence graphs/diagnoses, optimization experiment records, ML predictions, bandit events, accounts/approvals, and audit logs.
- Proposed core tables (see §13 for full data model): `query_metrics`, `table_metrics`, `plan_metrics`, `optimization_experiments`, `model_predictions`, `bandit_events`, plus application entities (users, database connections, diagnoses, approvals, audit log).
- Historical telemetry may additionally be exported to Parquet + queried via DuckDB for efficient offline ML training (proposed by source material; not mandatory for MVP).
- Retention policy: TBD — source documents do not specify exact retention windows; propose configurable retention (e.g. raw telemetry 30–90 days, aggregated/experiment records retained longer for model training) pending product decision.

**Shadow Database (Feature 2, ephemeral/per-experiment)**
- Production-shaped PostgreSQL copy, provisioned per experiment in one of three modes: full clone (`pg_dump`/`pg_restore`), logical-replication-based replica, or sampled clone (schema + representative 1–10% data sample) for fast iteration.
- Torn down after experiment completion; not a persistent store.

## 9. Safe Optimization & Verification

| Action type | Precondition | Simulation | Verification | Approval required | Rollback strategy | Post-change measurement |
|---|---|---|---|---|---|---|
| `CREATE INDEX` / `CREATE INDEX CONCURRENTLY` | Candidate passed HypoPG filter + ML prediction | Shadow DB replay (baseline vs candidate) | Paired statistical test, bootstrap CI, regression-rate check, Skeptic review, Policy Engine pass | Yes — production execution requires explicit human approval | Automatic `DROP INDEX` on canary threshold breach | Live canary window (p50/p95/p99, error rate, lock waits, CPU, IO, throughput, write latency) |
| `DROP INDEX` | Confirmed unused via `get_index_usage` evidence | Shadow DB replay to confirm no dependent query regresses | Same as above | Yes | Recreate index (requires original definition retained) | Live canary window |
| `ANALYZE` | Stale-statistics evidence from Vacuum/Planner agent | Counterfactual sandbox: re-run ANALYZE + EXPLAIN, confirm plan/estimate improves | Compare pre/post cardinality error | Advisory by default; low-risk — TBD whether auto-approved or still gated (source material treats ANALYZE as lower-risk than DDL but does not explicitly exempt it from approval) | No destructive rollback needed (ANALYZE is non-destructive) | Compare plan/estimate before vs. after |
| VACUUM-related actions | Vacuum lag/bloat evidence | N/A (VACUUM is generally non-destructive) — TBD if simulated | Compare dead-tuple ratio and bloat before/after | Advisory / TBD approval level | N/A (non-destructive) | Dead-tuple ratio, table size trend |
| Query rewrites | Rewrite candidate generated deterministically (predicate simplification, join elimination) | Shadow DB replay | Same statistical verification as indexes | Yes (application-level change) | Revert to original query text | Live comparison post-deployment |
| Configuration changes | Planner/config candidate (e.g. enable/disable join strategy, generic/custom plan) | Shadow DB replay under candidate config | Same statistical verification | Yes | Revert configuration value | Live canary window |

**Operation classification (per §9 of source docs / requested breakdown):**
- **Read-only:** All telemetry collection, diagnosis, evidence graph construction, forecasting.
- **Advisory:** ANALYZE/VACUUM recommendations pending explicit product decision on auto-approval (flagged TBD above); all "detected problem" and "recommended action" surfacing before simulation.
- **Simulated:** HypoPG filtering, shadow-DB replay, statistical verification — none of these touch the monitored production database's real data or schema.
- **Requires approval:** Any DDL (CREATE/DROP INDEX), query-serving config change, or query rewrite deployment to production.
- **Autonomous:** Monitoring, diagnosis, candidate generation, simulation, and automatic rollback on canary threshold breach (rollback itself does not require new human approval, since it reverts to the last-approved state).

**Contradiction/adversarial safeguards:** The Skeptic Agent's adversarial findings and the Policy Engine's deterministic thresholds sit outside LLM control — an LLM-favorable recommendation can still be rejected by the Policy Engine, and this rejection is final for that candidate.

## 10. Backend Architecture

- **API architecture:** REST(ful) API (framework not explicitly fixed by source docs beyond the recommended stack in §17) exposing connection management, diagnosis retrieval, recommendation/approval endpoints, and experiment/audit history.
- **Services:** Telemetry Collector (continuous polling of monitored DB via `asyncpg`), Evidence Engine, Anomaly Detection service, Agent Orchestrator (Supervisor + specialist agents), Simulation/Verification service (HypoPG, Shadow DB lifecycle, statistical testing), Forecasting/Bandit service, Policy Engine, Deployment/Canary service, ROI calculation service.
- **Workers/Background jobs:** Scheduled telemetry collection, scheduled forecasting runs, retraining jobs, canary monitoring windows, shadow-DB provisioning/teardown.
- **Queues:** TBD — source documents do not mandate a message queue; only include one if background job volume in the actual implementation requires it (per instruction not to over-specify infrastructure). Not confirmed as required.
- **WebSockets/SSE:** Recommended for live dashboard updates during canary monitoring windows and long-running simulations, so the user sees real-time progress — inferred as a reasonable requirement, not explicitly specified in source docs; flagged for confirmation.
- **Authentication:** User account authentication for the application itself (mechanism TBD — not specified in source docs). Separate credential handling for each monitored database connection (stored encrypted; see §14).
- **Authorization:** Role/permission model for who can approve production-modifying actions — TBD exact RBAC scheme, but approval-gating is a hard requirement (§9).
- **Database access:** Application services access the application DB directly; monitored-DB access is exclusively through the Telemetry Collector and Deployment/Canary service, using the least-privilege role configured at connection time.

## 11. Frontend Architecture

- **Main pages:** Dashboard (overview of connected databases, active problems), Database Connection flow (add connection, test connection, role/permission check), Monitoring UI (live telemetry, anomaly indicators), Investigation/Diagnosis UI (root-cause report, evidence graph, timeline), Recommendations UI (candidate optimizations with predicted impact/uncertainty), Simulation Results UI (statistical verification report, Skeptic findings, Policy verdict), Approval UI (explicit approve/reject action for production changes), Optimization History / Audit Trail, Cost/Performance Analytics (ROI, MAE-over-time improvement curve, forecast view).
- Exact frontend framework/technology is not specified in the source documents — TBD.

## 12. API Requirements

Endpoints below are inferred from the functional requirements; exact request/response schemas are TBD pending implementation. Method/path naming is illustrative.

| Method | Endpoint | Purpose | Auth |
|---|---|---|---|
| POST | `/api/connections` | Register a new monitored database connection (connection string or host/port/user/pass/SSL) | User session |
| POST | `/api/connections/{id}/test` | Test reachability, credentials, required permissions/extensions | User session |
| GET | `/api/connections/{id}/telemetry` | Retrieve recent telemetry summary | User session |
| GET | `/api/connections/{id}/diagnoses` | List detected problems / root-cause reports | User session |
| GET | `/api/diagnoses/{id}` | Full root-cause report incl. evidence graph, timeline | User session |
| GET | `/api/diagnoses/{id}/recommendations` | Candidate optimizations for a diagnosis | User session |
| POST | `/api/recommendations/{id}/simulate` | Trigger/re-trigger simulation (if not already run) | User session |
| GET | `/api/recommendations/{id}/verification` | Statistical verification + Skeptic + Policy verdict | User session |
| POST | `/api/recommendations/{id}/approve` | Human approval to proceed to canary deployment | User session (authorized role) |
| POST | `/api/recommendations/{id}/reject` | Reject a recommendation | User session |
| GET | `/api/deployments/{id}` | Canary status, live metrics, commit/rollback state | User session |
| GET | `/api/experiments` | Historical optimization experiment records (audit trail) | User session |
| GET | `/api/forecast/{connectionId}` | Degradation forecast / probability curve | User session |
| GET | `/api/models/performance` | MAE-over-time, calibration report | User session |

Authentication/authorization mechanism and detailed error schemas: TBD — not specified in source documents.

## 13. Data Model

Core entities (fields drawn directly from source-document dataset structures where specified):

**`query_metrics`** — timestamp, db_id, userid, queryid, query(_hash), calls, total/mean/min/max_exec_time, rows, shared_blks_hit/read/dirtied/written, temp_blks_read/written, wal_bytes, plans, planning_time.

**`table_metrics`** — timestamp, schema, table, row_count, table_size, index_size, seq_scans, seq_tup_read, idx_scans, idx_tup_fetch, dead_tuples, live_tuples, insert/update/delete_rate, last_(auto)analyze, last_(auto)vacuum.

**`plan_metrics`** — timestamp, query_id, plan_hash, node_types, estimated_rows, actual_rows, estimated_cost, actual_time, buffer_hits, buffer_reads, join_types, parallel_workers.

**`optimization_experiments`** — experiment_id, timestamp, query_id, table, strategy, candidate_sql, baseline_latency/p95/cpu/io, candidate_latency/p95/cpu/io, predicted_latency_delta, actual_latency_delta, prediction_error, success (bool), risk, rollback (bool).

**`model_predictions`** — prediction_id, model_version, experiment_id, prediction, lower_bound, upper_bound, confidence, actual, absolute_error.

**`bandit_events`** — context, action, propensity, reward, success, model_version.

**Application entities (inferred, not explicitly detailed in source docs — TBD exact fields):** `users`/`accounts`, `database_connections` (encrypted credentials, connection metadata, permission-check status), `diagnoses` (root-cause report, evidence graph reference, timeline), `evidence_graph_nodes/edges`, `approvals` (who approved, when, what action), `audit_log` (all production-modifying actions with full context), `deployments`/`canary_runs` (status, live metrics, commit/rollback outcome).

**Relationships:** A `database_connections` row has many `diagnoses`; a `diagnoses` row has many candidate `optimization_experiments`; an `optimization_experiments` row has one or more `model_predictions` and, if executed, one `deployments`/`canary_runs` record and one `audit_log` entry; `bandit_events` reference the workload context and chosen action linked back to an `optimization_experiments` outcome.

## 14. Security

- **Database credentials:** Stored encrypted at rest in the application database; never logged in plaintext; never exposed to the LLM reasoning layer directly (agents call scoped tools, not raw connection strings).
- **Least privilege:** Users are directed to provide a dedicated read-only monitoring role for the monitored database rather than admin/owner credentials; production-modifying actions use a separately scoped, more privileged credential only invoked by the Deployment Agent after policy pass + approval.
- **Secrets management:** TBD specific mechanism (e.g. vault/KMS) — not specified in source docs, but encryption-at-rest for credentials is a hard requirement.
- **Encryption:** Credentials and sensitive telemetry encrypted at rest; connections to monitored databases should use SSL/TLS where supported (SSL settings are an explicit part of the connection flow).
- **Authentication/Authorization:** Application-level user auth (mechanism TBD); production-approval actions should be restricted to an authorized role (exact RBAC TBD).
- **Audit logs:** Every production-modifying action (DDL execution, config change, canary commit/rollback) is recorded with actor, timestamp, policy verdict, and outcome — see `audit_log` in §13.
- **SQL execution safety:** No LLM-generated raw SQL is ever executed directly against the monitored production database; all execution goes through the structured action → policy engine → guarded execution tool pipeline (§9). All simulation activity is isolated to HypoPG (in-planner only, no real storage/data impact) or the ephemeral Shadow DB — never the monitored DB's real data.
- **Tenant isolation:** Multi-tenant data (telemetry, diagnoses, experiments) must be scoped per user/organization in the application database — exact isolation mechanism (row-level security vs. schema-per-tenant) TBD, not specified in source docs.
- **Sensitive data handling:** Query text/parameters captured for fingerprinting and replay may contain sensitive data (e.g. literal values in `WHERE` clauses) — normalization/redaction approach for query text before storage or LLM exposure is TBD, flagged as an open question (§24).

## 15. Observability

- **Logs:** Telemetry collection job logs, agent execution logs (per-agent tool calls and outputs), simulation/verification run logs, deployment/canary execution logs.
- **Metrics:** System health (collector uptime, collection latency), model performance (MAE/RMSE/calibration over time per §7/§21), canary live metrics (p50/p95/p99, error rate, lock waits, CPU, IO, throughput, write latency), bandit metrics (cumulative reward, regret).
- **Traces:** Recommended for the multi-agent orchestration flow (per-investigation trace from telemetry → detection → agent outputs → supervisor verdict) so a given diagnosis can be replayed/debugged — inferred as best practice, not explicitly specified in source docs.
- **Agent execution logs:** Structured record of each agent's tool calls, evidence produced, and confidence — feeding both the UI's evidence graph and internal debugging.
- **Optimization audit trail:** Full experiment lifecycle (candidate → HypoPG → ML prediction → shadow simulation → statistical verification → Skeptic → Policy verdict → approval → canary → commit/rollback) retained per `optimization_experiments` + `audit_log`.
- **Model decisions:** Every prediction stored with model_version, prediction, interval, and (once known) actual outcome and error (`model_predictions` table) — this is both an observability and ML-training artifact.
- **Errors/Alerts:** TBD specific alerting thresholds/channels — not specified in source docs; recommend alerting at minimum on: collector failures, canary automatic rollback events, and detected model drift.

## 16. Infrastructure & Deployment

- **Docker:** Used for the Database Fault Laboratory / Optimization Laboratory (Postgres + workload generator + fault injector + telemetry collector + ground-truth recorder), and reasonably for the application services themselves.
- **PostgreSQL:** Both the application database and, per Shadow DB provisioning, ephemeral shadow instances. PostgreSQL 18 referenced in source material for its monitoring/statistics facilities (`pg_stat_statements`, `pg_stat_activity`, `pg_locks`, `pg_stat_progress_vacuum`, `pg_stats`); the monitored database's actual version will vary by user and the system should be resilient to differing minor versions.
- **Neon:** One possible hosting choice for the application's own PostgreSQL database — not the user's monitored database unless the user's database also happens to be hosted on Neon.
- **Redis/queues:** Not confirmed as required by source documents — include only if implementation-level background job volume necessitates it (per explicit instruction not to over-add infrastructure).
- **Vector database:** Not required — no feature in the source documents relies on embedding-based retrieval; evidence is structured/tabular, not semantic search.
- **Cloud deployment:** TBD — not specified.
- **CI/CD:** TBD — not specified; recommended given the model promotion workflow (§7) needs a repeatable pipeline for training/evaluating/promoting new model versions, but exact tooling is not specified in source docs.
- **Monitoring:** MLflow for experiment/model tracking (explicitly specified); Evidently or an equivalent framework optionally referenced for drift monitoring; application-level monitoring stack otherwise TBD.

## 17. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | TBD | Not specified in source documents |
| Backend | Python 3.12+, FastAPI, asyncpg, SQLAlchemy, Pydantic | API services, telemetry collection, DB access |
| Database | PostgreSQL (application DB), PostgreSQL (monitored DB, version varies by user), ephemeral Shadow DB (PostgreSQL) | Application storage, user's monitored database, isolated simulation environment |
| AI/LLM | LLM used for reasoning/orchestration over structured evidence (specific provider/model not specified in source docs — TBD) | Evidence reconciliation, causal narrative, agent orchestration |
| ML | NumPy, Pandas, Polars, scikit-learn, SciPy, LightGBM, XGBoost/CatBoost (candidates), PyTorch (for optional LSTM/TCN/plan-tree models), MLflow | Anomaly detection, root-cause classification, outcome prediction, forecasting, experiment tracking |
| Agents | Graph-based agent orchestration (LangGraph recommended in source material) | Multi-agent investigation, simulation, and deployment orchestration |
| Vector DB | Not used | Not required — no semantic retrieval feature in scope |
| Queue | TBD / not confirmed required | Background job processing if volume requires it |
| Infrastructure | Docker (fault/optimization laboratory + services), optional DuckDB for offline analytics over Parquet-exported telemetry | Training-data generation, offline ML training |
| Monitoring | MLflow (model tracking), Evidently (optional, drift monitoring) | Model performance, calibration, drift |

## 18. Non-Functional Requirements

- **Performance:** Telemetry collection must be lightweight enough not to materially burden the monitored production database — exact latency/overhead budget TBD, not specified in source docs.
- **Scalability:** TBD — number of concurrent monitored databases per deployment not specified.
- **Reliability:** Automatic rollback on canary threshold breach is a hard reliability requirement (§9); telemetry collection failures must not silently stop monitoring without alerting (see §15, TBD alert specifics).
- **Security:** Per §14 — least-privilege credentials, encrypted secrets, no unapproved production writes.
- **Availability:** TBD — no SLA specified in source documents.
- **Latency:** TBD for API/dashboard responsiveness; canary monitoring window duration referenced as ~15 minutes (example, not a hard spec).
- **Cost:** Feature 4 (ROI) is the only cost-related feature, and its cost model is itself TBD (§5).
- **Data retention:** TBD exact windows (§8) — propose configurable retention policy pending product decision.

## 19. MVP

Based on what the source documents establish as the "must build first" spine (evidence pipeline → simulation → approval, with the predictive/bandit layer as a natural second phase):

**MVP scope**
1. Database connection flow (connect, test connection, permission/extension check) for a single monitored PostgreSQL database per user.
2. Continuous read-only telemetry collection (`pg_stat_statements`, `pg_stat_activity`, `pg_locks`, `pg_stat_user_tables`, `pg_stat_user_indexes`, `pg_stat_progress_vacuum`, `EXPLAIN` plan capture).
3. Deterministic evidence engine (plan diff, cardinality error, lock graph, vacuum/bloat metrics) — even before the full ML anomaly-detection layer, this is the credibility foundation.
4. Baseline multivariate anomaly detection (Isolation Forest + robust z-score) sufficient to flag "something changed."
5. Core specialist agents (Planner, Concurrency, Vacuum, I/O/Buffer, Schema/Index) + Supervisor reconciliation producing a root-cause report with confidence and evidence.
6. Deterministic candidate generation limited to indexes + statistics actions (the source material explicitly calls these the strongest supported action types for an initial build).
7. HypoPG fast filtering + Shadow DB simulation (at minimum, sampled-clone mode) + paired statistical verification + regression-rate check.
8. Skeptic Agent adversarial review + Policy Engine hard-rule gating.
9. Human approval gate for any production-modifying action.
10. Canary deployment with defined rollback thresholds and automatic rollback.
11. Optimization audit trail / history UI.
12. Root-Cause Fault Laboratory sufficient to generate initial training data for the anomaly/root-cause classifier and the outcome predictor.

**Explicitly deferred out of MVP** (see §20): full L1–L4 predictive ML stack (forecasting, contextual bandit, offline policy evaluation), Feature 4 ROI translation, plan-tree neural network ensemble, Feast feature store, multi-database-engine support, drift-monitoring automation (Evidently), full canary live-metrics dashboarding beyond basic pass/fail.

## 20. Future Roadmap

- Full predictive ML stack: L1 Workload Forecasting with degradation-probability curves, L2 Optimization Outcome Model with full uncertainty quantification, L3 Contextual Bandit strategy selection (with mandatory offline policy evaluation before live use), L4 calibration/drift monitoring dashboard.
- Feature 4 Cost-to-Dollar ROI translation once a concrete pricing/cost model is defined.
- Plan-tree neural network encoder fused with tabular model for the Query Performance Delta Predictor.
- Broader candidate-optimization types: query rewrites, planner/config changes at production scale.
- Feature store (Feast) if online/offline feature consistency becomes a bottleneck.
- Multi-database support beyond a single connection per user (TBD if multiple simultaneous monitored databases per account is in scope).
- Expanded fault-injection matrix / continuously growing self-generated training dataset.

## 21. Success Metrics

All targets below are **proposed**, not sourced from explicit target numbers in the documents unless noted, and should be validated against real usage.

- **Root-cause classification accuracy:** precision/recall/F1 per fault class against Fault-Laboratory ground truth (proposed target: TBD — no numeric target given in source docs).
- **Prediction accuracy (forecasting/outcome models):** MAE trending down across iterations — source material gives an illustrative (not guaranteed) example curve of MAE improving from ~16.7% → ~10.4% → ~6.8% across model versions; treat as illustrative only, not a committed target.
- **Optimization success rate:** % of approved, deployed optimizations that reach COMMIT rather than automatic ROLLBACK.
- **Performance improvement:** measured p95/p50 latency reduction per committed optimization (from canary live metrics).
- **False-positive rate:** % of flagged anomalies/diagnoses that do not correspond to a real, actionable problem.
- **Rollback rate:** % of canary deployments that trigger automatic rollback — should trend down over time as prediction/verification improves.
- **User approval rate:** % of surfaced recommendations that users approve (a proxy for recommendation trustworthiness).
- **Calibration accuracy:** predicted-confidence vs. actual-coverage gap across confidence buckets (target: small gap, e.g. within a few percentage points — proposed, not sourced).
- **Cost reduction:** dependent on Feature 4 being implemented; TBD until the ROI cost model is defined.

## 22. Acceptance Criteria

(Consolidated from per-feature acceptance criteria in §5; repeated here as the implementation-ready checklist.)

- Root-cause reports are always evidence-traceable; no unsupported LLM narrative is presented as fact.
- No optimization is presented as "verified" without having passed HypoPG → ML prediction → Shadow DB simulation → statistical verification → Skeptic review → Policy Engine, in that order.
- No production-modifying action executes without a corresponding human approval record.
- Every canary deployment has defined rollback thresholds and rolls back automatically on breach without requiring human input.
- Every optimization experiment (predicted vs. actual) produces a retrievable training record.
- Model promotion only occurs when the new model version measurably outperforms the currently deployed version (tracked in MLflow).
- Bandit-influenced recommendations do not appear in the product until offline policy evaluation has been completed for that policy version.
- Every production-modifying action has a complete, retrievable audit log entry (actor, action, policy verdict, timestamp, outcome).

## 23. Risks & Mitigations

| Risk | Category | Mitigation |
|---|---|---|
| LLM hallucinated root cause presented as fact | AI | Evidence-traceability requirement (§22); deterministic evidence engine + counterfactual validation before raising confidence |
| Bad optimization causes production outage | Database/Operational | Mandatory simulation + statistical verification + Skeptic + Policy Engine + canary + automatic rollback (§9) |
| Insufficient training data for ML models at launch | AI | Self-generated Fault/Optimization Laboratory (§7) to bootstrap training data independent of real user volume |
| Telemetry collection overloads the monitored production database | Database/Operational | Read-only, lightweight polling design; TBD explicit overhead budget to be defined during implementation |
| Overprivileged database credentials leaked or misused | Security | Enforce dedicated least-privilege read-only role for monitoring; separately scoped, narrowly used credential for execution (§14) |
| Bandit recommends untested strategy before it has enough data | AI | Rollout gating: rule-based → supervised → bandit → offline-evaluated before live influence (§7) |
| Statistical verification underpowered (too few paired samples) leads to false confidence | Technical | Verdict downgraded to CONDITIONAL rather than VERIFIED when sample size is insufficient (§5, Feature 2) |
| Sensitive data exposure via captured query text/parameters | Security | Redaction/normalization approach TBD — flagged as open question (§24) |
| Workload drift silently degrades model accuracy | AI | Drift detection (feature/prediction/error) triggers reduced confidence + retraining recommendation, not silent continued use (§7) |
| Tenant data leakage in a multi-tenant deployment | Security | Tenant isolation requirement (§14) — exact mechanism TBD, must be resolved before multi-tenant launch |

## 24. Open Questions / TBD

- Product name.
- Exact target user segment (company size, self-serve vs. enterprise).
- Frontend framework/technology.
- Application authentication mechanism and RBAC scheme for approval permissions.
- Exact retention policy windows for telemetry/experiment data.
- Whether ANALYZE/VACUUM actions are fully autonomous (Advisory) or still require explicit human approval like DDL.
- Feature 4's exact cost-to-dollar mapping formula and pricing data source.
- Whether a message queue (Redis or similar) is actually needed — depends on implementation-time background job volume.
- Model serving architecture (batch vs. real-time inference service).
- Sensitive-data redaction approach for captured query text/parameters used in fingerprinting, replay, and LLM-facing evidence.
- Exact SLA/availability/latency targets.
- Whether multiple simultaneous monitored databases per user account is supported in MVP or deferred.
- CI/CD tooling and cloud deployment target.
- Numeric target thresholds for root-cause classification accuracy and other §21 metrics — source documents give illustrative, not committed, example numbers.
