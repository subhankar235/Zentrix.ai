"""Feature 3 L4 Retrain Worker & Closed-Loop Learning.

Orchestrates the feedback loop, prediction error tracking (MAE/RMSE), calibration
monitoring across confidence buckets, drift detection, automated retraining triggers,
and MLflow-tracked model promotion.

Reference: ARCHITECTURE.md §4, §8 & PRD.md §5 Feature 3 L4, §7, §21, §22.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.ml.bandit.policy import ContextualThompsonSamplingBandit, RolloutPhase
from app.ml.forecasting.train import train as train_l1_forecasting
from app.models.audit import AuditLog
from app.models.experiment import BanditEvent, ModelPrediction, OptimizationExperiment
from app.models.forecast import ModelDriftReport

logger = get_logger(__name__)

CALIBRATION_BUCKETS = [
    (0.0, 0.20),
    (0.20, 0.40),
    (0.40, 0.60),
    (0.60, 0.80),
    (0.80, 1.00),
]


async def compute_prediction_errors_and_calibration(
    db: AsyncSession,
) -> dict[str, Any]:
    """Compute prediction errors (MAE, RMSE) and calibration coverage across 5 confidence buckets."""
    # Query all predictions joined with their experiments
    stmt = (
        select(ModelPrediction)
        .options(selectinload(ModelPrediction.experiment))
        .order_by(ModelPrediction.created_at.desc())
    )
    result = await db.execute(stmt)
    predictions = list(result.scalars().all())

    if not predictions:
        return {
            "total_labeled": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "calibration_error": 0.0,
            "calibration_report": [],
            "models": {},
        }

    version_errors: dict[str, list[float]] = {}
    version_squared_errors: dict[str, list[float]] = {}
    bucket_counts: dict[str, int] = {f"{low:.1f}-{high:.1f}": 0 for low, high in CALIBRATION_BUCKETS}
    bucket_hits: dict[str, int] = {f"{low:.1f}-{high:.1f}": 0 for low, high in CALIBRATION_BUCKETS}

    all_abs_errors: list[float] = []
    all_sq_errors: list[float] = []

    for pred in predictions:
        exp = pred.experiment
        if exp is None:
            continue

        # Actual delta observed from experiment (candidate_p95 - baseline_p95)
        actual_delta = exp.candidate_p95 - exp.baseline_p95
        abs_err = abs(actual_delta - pred.prediction)
        sq_err = (actual_delta - pred.prediction) ** 2

        # Update prediction record if not populated
        if pred.actual is None or pred.absolute_error is None:
            pred.actual = actual_delta
            pred.absolute_error = abs_err
            exp.actual_latency_delta = actual_delta
            exp.prediction_error = abs_err

        v = pred.model_version or "v1"
        version_errors.setdefault(v, []).append(abs_err)
        version_squared_errors.setdefault(v, []).append(sq_err)
        all_abs_errors.append(abs_err)
        all_sq_errors.append(sq_err)

        # Calibration tracking: does the interval [lower_bound, upper_bound] cover actual outcome?
        conf = float(np.clip(pred.confidence, 0.0, 1.0))
        is_covered = pred.lower_bound <= actual_delta <= pred.upper_bound

        for low, high in CALIBRATION_BUCKETS:
            if (low <= conf < high) or (high == 1.0 and conf == 1.0):
                b_name = f"{low:.1f}-{high:.1f}"
                bucket_counts[b_name] += 1
                if is_covered:
                    bucket_hits[b_name] += 1
                break

    await db.commit()

    # Build calibration table across >=5 buckets per PRD §21
    calibration_report: list[dict[str, Any]] = []
    total_n = len(all_abs_errors)
    ece = 0.0

    for low, high in CALIBRATION_BUCKETS:
        b_name = f"{low:.1f}-{high:.1f}"
        cnt = bucket_counts[b_name]
        mid_conf = (low + high) / 2.0
        emp_coverage = (bucket_hits[b_name] / cnt) if cnt > 0 else mid_conf

        if cnt > 0 and total_n > 0:
            ece += (cnt / total_n) * abs(mid_conf - emp_coverage)

        calibration_report.append({
            "bucket": b_name,
            "predicted_confidence": float(mid_conf),
            "empirical_coverage": float(emp_coverage),
            "sample_count": cnt,
        })

    model_metrics: dict[str, dict[str, float]] = {}
    for v, errs in version_errors.items():
        sq_errs = version_squared_errors.get(v, errs)
        model_metrics[v] = {
            "mae": float(np.mean(errs)),
            "rmse": float(np.sqrt(np.mean(sq_errs))),
            "count": len(errs),
        }

    return {
        "total_labeled": len(all_abs_errors),
        "mae": float(np.mean(all_abs_errors)) if all_abs_errors else 0.0,
        "rmse": float(np.sqrt(np.mean(all_sq_errors))) if all_sq_errors else 0.0,
        "expected_calibration_error": float(ece),
        "calibration_report": calibration_report,
        "models": model_metrics,
    }


def compute_feature_drift_score(
    reference: Sequence[float],
    current: Sequence[float],
) -> float:
    """Compute two-sample Kolmogorov-Smirnov drift score between reference and current samples."""
    if len(reference) < 5 or len(current) < 5:
        return 0.0

    # KS statistic D in [0, 1]
    res = stats.ks_2samp(reference, current)
    return float(res.statistic)


async def detect_feature_and_prediction_drift(
    db: AsyncSession,
    drift_threshold: float = 0.30,
) -> ModelDriftReport:
    """Run data and prediction drift monitoring across feature distributions."""
    now = datetime.now(timezone.utc)
    split_time = now - timedelta(days=7)

    # 1. Fetch recent vs reference experiments
    ref_stmt = select(OptimizationExperiment).where(OptimizationExperiment.timestamp < split_time).limit(100)
    curr_stmt = select(OptimizationExperiment).where(OptimizationExperiment.timestamp >= split_time).limit(100)

    ref_res = await db.execute(ref_stmt)
    curr_res = await db.execute(curr_stmt)

    ref_exps = list(ref_res.scalars().all())
    curr_exps = list(curr_res.scalars().all())

    feature_drifts: dict[str, float] = {}

    for feat in ["baseline_p95", "candidate_p95", "baseline_cpu", "baseline_io"]:
        ref_vals = [float(getattr(e, feat, 0.0)) for e in ref_exps]
        curr_vals = [float(getattr(e, feat, 0.0)) for e in curr_exps]
        score = compute_feature_drift_score(ref_vals, curr_vals)
        feature_drifts[feat] = score

    # Prediction drift on predicted_latency_delta
    ref_preds = [float(e.predicted_latency_delta) for e in ref_exps]
    curr_preds = [float(e.predicted_latency_delta) for e in curr_exps]
    pred_drift_score = compute_feature_drift_score(ref_preds, curr_preds)

    dataset_drift_score = float(np.mean(list(feature_drifts.values()))) if feature_drifts else 0.0
    is_drift = bool(dataset_drift_score >= drift_threshold or pred_drift_score >= drift_threshold)

    report = ModelDriftReport(
        model_name="forecasting_l1_delta_l2",
        model_version="current_promoted",
        dataset_drift_score=dataset_drift_score,
        prediction_drift_score=pred_drift_score,
        metrics_payload={
            "feature_drifts": feature_drifts,
            "reference_samples": len(ref_exps),
            "current_samples": len(curr_exps),
            "evaluated_at": now.isoformat(),
        },
        is_drift_detected=is_drift,
        created_at=now,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return report


def evaluate_model_promotion(
    current_mae: float,
    candidate_mae: float,
    min_improvement_ratio: float = 0.03,
) -> tuple[bool, str]:
    """Evaluate whether candidate model should be promoted over currently promoted model.

    PRD.md §22 Acceptance Criteria: MAE must be strictly non-increasing / improved.
    """
    if current_mae <= 0.0:
        return True, "Initial model promotion (no baseline MAE exists)"

    improvement = (current_mae - candidate_mae) / current_mae
    if improvement >= min_improvement_ratio:
        return True, f"Candidate MAE ({candidate_mae:.3f}) improved by {improvement * 100:.1f}% over current ({current_mae:.3f})"

    return False, f"Candidate MAE ({candidate_mae:.3f}) failed to improve by required {min_improvement_ratio * 100:.0f}% over current ({current_mae:.3f})"


async def evaluate_bandit_promotion(
    db: AsyncSession,
) -> dict[str, Any]:
    """Evaluate logged bandit decisions using Inverse Propensity Scoring (IPS)."""
    stmt = select(BanditEvent).order_by(BanditEvent.created_at.desc()).limit(200)
    result = await db.execute(stmt)
    events = list(result.scalars().all())

    logged_events = [
        {
            "context": ev.context,
            "action": ev.action,
            "propensity": ev.propensity,
            "reward": ev.reward or 0.0,
        }
        for ev in events
    ]

    bandit = ContextualThompsonSamplingBandit()
    ips_report = bandit.evaluate_offline_ips(logged_events, min_effective_sample_size=10)

    return ips_report


async def run_retrain_cycle(
    db: AsyncSession,
    force: bool = False,
    min_new_experiments: int = 20,
) -> dict[str, Any]:
    """Execute complete closed-loop learning & retraining cycle."""
    now = datetime.now(timezone.utc)
    logger.info("Executing closed-loop learning retrain cycle")

    # 1. Update MAE/RMSE prediction errors and calibration table
    error_summary = await compute_prediction_errors_and_calibration(db)

    # 2. Run drift detection
    drift_report = await detect_feature_and_prediction_drift(db)

    # 3. Evaluate retrain triggers
    n_labeled = error_summary["total_labeled"]
    is_drift = drift_report.is_drift_detected

    should_retrain = force or (n_labeled >= min_new_experiments) or is_drift
    retrain_reason = "FORCED" if force else ("DRIFT_TRIGGERED" if is_drift else ("VOLUME_TRIGGERED" if n_labeled >= min_new_experiments else "SKIPPED"))

    models_trained: dict[str, Any] = {}

    if should_retrain:
        logger.info(f"Retraining triggered: reason={retrain_reason}, n_labeled={n_labeled}")

        # Retrain L1 forecasting
        new_version_tag = f"l1_{now.strftime('%Y%m%d_%H%M%S')}"
        l1_result = train_l1_forecasting(version=new_version_tag)
        cand_mae = l1_result["metrics"]["mae"]

        curr_mae = error_summary.get("mae", 0.0)
        is_promoted, promo_reason = evaluate_model_promotion(curr_mae, cand_mae)

        models_trained["l1_forecasting"] = {
            "version": new_version_tag,
            "candidate_mae": cand_mae,
            "is_promoted": is_promoted,
            "reason": promo_reason,
        }

        # Evaluate L3 bandit offline policy
        bandit_eval = await evaluate_bandit_promotion(db)
        models_trained["l3_bandit"] = bandit_eval

        # Audit log the retraining event
        audit = AuditLog(
            user_id=None,
            action_type="MODEL_RETRAIN_CYCLE",
            target_entity="ml_model",
            target_id=new_version_tag,
            details={
                "trigger_reason": retrain_reason,
                "n_labeled": n_labeled,
                "l1_results": models_trained.get("l1_forecasting", {}),
                "is_drift_detected": is_drift,
            },
            timestamp=now,
        )
        db.add(audit)
        await db.commit()

    return {
        "status": "COMPLETED",
        "timestamp": now.isoformat(),
        "error_summary": error_summary,
        "drift_detected": is_drift,
        "retrain_triggered": should_retrain,
        "retrain_reason": retrain_reason,
        "models_trained": models_trained,
    }


async def run_retrain_worker(
    stop_event: asyncio.Event | None = None,
    poll_interval: int | None = None,
    session_factory: Any = None,
) -> None:
    """Continuous background worker loop executing closed-loop learning and retraining cycles."""
    import asyncio
    from app.db.session import async_session_factory

    factory = session_factory or async_session_factory
    interval = poll_interval or 3600  # Default 1 hour between checks
    stop = stop_event or asyncio.Event()

    logger.info(f"Starting Retrain & Closed-Loop Learning worker (poll_interval={interval}s)")
    while not stop.is_set():
        try:
            async with factory() as db:
                await run_retrain_cycle(db, force=False)
        except Exception as exc:
            logger.error(f"Retrain worker error during cycle execution: {exc}", exc_info=True)

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def main() -> None:
    import asyncio
    import signal

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError):
            pass

    await run_retrain_worker(stop_event=stop_event)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

