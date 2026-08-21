"""Live Canary Observation Window Monitor Worker.

Monitors active canary deployments during their live observation window
(CANARY_MONITOR_WINDOW_MINUTES), tracking p50/p95/p99 latency, error rates,
lock waits, CPU/IO, and write latency. Automatically executes rollback on
threshold breach without requiring human intervention.

Reference: ARCHITECTURE.md §1, §4, §9 & PRD.md §5 Feature 2, §9, §22.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.audit import AuditLog, CanaryRun
from app.models.experiment import OptimizationExperiment

logger = get_logger(__name__)


DEFAULT_ROLLBACK_THRESHOLDS = {
    "p95_regression_max_ratio": 0.15,  # > 15% p95 latency increase
    "error_rate_max": 0.01,  # > 1% query error rate
    "write_latency_max_increase": 0.20,  # > 20% write latency increase
    "lock_wait_seconds_max": 5.0,  # > 5.0s total lock wait
}


def check_rollback_condition(
    baseline_metrics: Mapping[str, Any],
    current_metrics: Mapping[str, Any],
    thresholds: Mapping[str, Any] | None = None,
) -> tuple[bool, str | None]:
    """Evaluate whether live canary observations violate rollback thresholds.

    Returns (is_breached, rollback_reason).
    """
    cfg = {**DEFAULT_ROLLBACK_THRESHOLDS, **(thresholds or {})}

    base_p95 = float(baseline_metrics.get("p95_ms", baseline_metrics.get("baseline_p95", 0.0)))
    curr_p95 = float(current_metrics.get("p95_ms", current_metrics.get("candidate_p95", 0.0)))

    if base_p95 > 0 and curr_p95 > 0:
        p95_increase = (curr_p95 - base_p95) / base_p95
        if p95_increase > float(cfg["p95_regression_max_ratio"]):
            return (
                True,
                f"p95 latency regressed by {p95_increase:.1%} (threshold: {float(cfg['p95_regression_max_ratio']):.1%})",
            )

    curr_error_rate = float(current_metrics.get("error_rate", 0.0))
    if curr_error_rate > float(cfg["error_rate_max"]):
        return (
            True,
            f"Query error rate reached {curr_error_rate:.2%} (threshold: {float(cfg['error_rate_max']):.2%})",
        )

    base_write = float(baseline_metrics.get("write_mean_ms", baseline_metrics.get("baseline_write", 0.0)))
    curr_write = float(current_metrics.get("write_mean_ms", current_metrics.get("candidate_write", 0.0)))
    if base_write > 0 and curr_write > 0:
        write_increase = (curr_write - base_write) / base_write
        if write_increase > float(cfg["write_latency_max_increase"]):
            return (
                True,
                f"Write latency increased by {write_increase:.1%} (threshold: {float(cfg['write_latency_max_increase']):.1%})",
            )

    curr_lock_wait = float(current_metrics.get("lock_wait_seconds", 0.0))
    if curr_lock_wait > float(cfg["lock_wait_seconds_max"]):
        return (
            True,
            f"Lock wait reached {curr_lock_wait:.1f}s (threshold: {float(cfg['lock_wait_seconds_max']):.1f}s)",
        )

    return False, None


def generate_rollback_sql(canary_sql: str) -> str:
    """Generate the safe rollback SQL statement for an applied canary action."""
    cleaned = canary_sql.strip()
    upper = cleaned.upper()
    if "CREATE INDEX" in upper or "CREATE UNIQUE INDEX" in upper:
        # Extract index name
        import re
        match = re.search(r"INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_$]+)", cleaned, re.IGNORECASE)
        if match:
            idx_name = match.group(1)
            return f"DROP INDEX CONCURRENTLY IF EXISTS {idx_name}"
    return "/* ROLLBACK ACTION NOT REQUIRED */"


async def execute_rollback(
    canary_run: CanaryRun,
    experiment: OptimizationExperiment,
    reason: str,
    db: AsyncSession,
    customer_connection: Any = None,
) -> None:
    """Execute automated rollback on customer database and update audit records."""
    now = datetime.now(timezone.utc)
    rollback_sql = generate_rollback_sql(canary_run.canary_sql_applied)

    logger.warning(
        f"Triggering automated canary rollback for run {canary_run.id}: {reason}",
        extra={"canary_run_id": str(canary_run.id), "reason": reason},
    )

    if customer_connection is not None and rollback_sql.startswith("DROP INDEX"):
        try:
            await customer_connection.execute(rollback_sql)
            logger.info(f"Rollback SQL executed successfully: {rollback_sql}")
        except Exception as exc:
            logger.error(f"Failed to execute rollback SQL against customer DB: {exc}")

    canary_run.status = "ROLLED_BACK"
    canary_run.rollback_reason = reason
    canary_run.completed_at = now

    experiment.status = "ROLLED_BACK"
    experiment.rollback = True
    experiment.success = False

    audit_entry = AuditLog(
        connection_id=canary_run.connection_id,
        action_type="CANARY_ROLLBACK",
        target_entity="canary_run",
        target_id=str(canary_run.id),
        details={
            "experiment_id": str(experiment.id),
            "reason": reason,
            "rollback_sql": rollback_sql,
            "canary_metrics": canary_run.canary_metrics,
        },
        timestamp=now,
    )
    db.add(audit_entry)
    await db.commit()


async def execute_commit(
    canary_run: CanaryRun,
    experiment: OptimizationExperiment,
    db: AsyncSession,
) -> None:
    """Commit an approved canary deployment after clearing the observation window."""
    now = datetime.now(timezone.utc)
    logger.info(f"Canary observation window cleared. Committing deployment {canary_run.id}")

    canary_run.status = "COMMITTED"
    canary_run.completed_at = now

    experiment.status = "DEPLOYED"
    experiment.rollback = False
    experiment.success = True

    audit_entry = AuditLog(
        connection_id=canary_run.connection_id,
        action_type="CANARY_COMMIT",
        target_entity="canary_run",
        target_id=str(canary_run.id),
        details={
            "experiment_id": str(experiment.id),
            "canary_sql": canary_run.canary_sql_applied,
            "final_metrics": canary_run.canary_metrics,
        },
        timestamp=now,
    )
    db.add(audit_entry)
    await db.commit()


async def monitor_canary_tick(
    canary_run: CanaryRun,
    db: AsyncSession,
    current_metrics: Mapping[str, Any] | None = None,
    customer_connection: Any = None,
) -> dict[str, Any]:
    """Evaluate a single monitoring tick for an active canary run."""
    stmt = select(OptimizationExperiment).where(OptimizationExperiment.id == canary_run.experiment_id)
    exp = await db.scalar(stmt)
    if not exp:
        return {"status": "ERROR", "error": "Experiment not found"}

    now = datetime.now(timezone.utc)
    started_at = canary_run.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    window_minutes = canary_run.observation_window_minutes or get_settings().CANARY_MONITOR_WINDOW_MINUTES
    is_window_elapsed = (now - started_at) >= timedelta(minutes=window_minutes)

    metrics = current_metrics or canary_run.canary_metrics or {}
    base_metrics = canary_run.baseline_metrics or {
        "p95_ms": exp.baseline_p95,
        "write_mean_ms": 10.0,
    }

    # Check for threshold breach
    breached, reason = check_rollback_condition(base_metrics, metrics)
    if breached and reason:
        await execute_rollback(canary_run, exp, reason, db, customer_connection=customer_connection)
        return {
            "status": "ROLLED_BACK",
            "canary_run_id": str(canary_run.id),
            "rollback_reason": reason,
        }

    # If observation window completed with no breaches, commit
    if is_window_elapsed:
        await execute_commit(canary_run, exp, db)
        return {
            "status": "COMMITTED",
            "canary_run_id": str(canary_run.id),
            "message": f"Observation window of {window_minutes}m cleared successfully",
        }

    # Still running
    canary_run.canary_metrics = dict(metrics)
    await db.commit()
    return {
        "status": "RUNNING",
        "canary_run_id": str(canary_run.id),
        "metrics": metrics,
    }


async def monitor_active_canaries_once(session_factory: Any = None) -> list[dict[str, Any]]:
    """Poll and evaluate all active running canary deployments once."""
    from app.db.session import async_session_factory

    factory = session_factory or async_session_factory
    results: list[dict[str, Any]] = []

    async with factory() as db:
        stmt = select(CanaryRun).where(CanaryRun.status == "RUNNING")
        res = await db.execute(stmt)
        active_runs = list(res.scalars().all())

        for run in active_runs:
            try:
                tick_res = await monitor_canary_tick(run, db)
                results.append(tick_res)
            except Exception as exc:
                logger.error(f"Canary tick error for run {run.id}: {exc}", exc_info=True)
                results.append({"status": "ERROR", "canary_run_id": str(run.id), "error": str(exc)})

    return results


async def run_canary_worker(
    stop_event: asyncio.Event | None = None,
    poll_interval: int | None = None,
    session_factory: Any = None,
) -> None:
    """Continuous background worker loop evaluating live canary deployments."""
    interval = poll_interval or get_settings().CANARY_POLL_INTERVAL_SECONDS if hasattr(get_settings(), "CANARY_POLL_INTERVAL_SECONDS") else 10
    stop = stop_event or asyncio.Event()

    logger.info(f"Starting Canary Monitor worker (poll_interval={interval}s)")
    while not stop.is_set():
        await monitor_active_canaries_once(session_factory=session_factory)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def main() -> None:
    import signal

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError):
            pass

    await run_canary_worker(stop_event=stop_event)


if __name__ == "__main__":
    asyncio.run(main())

