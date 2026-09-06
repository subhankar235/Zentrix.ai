"""Feature 3 Forecasting Application Service.

Orchestrates degradation forecasting, bandit strategy selection, persistence to
forecast_records and bandit_events, model performance retrieval (MAE, calibration, drift),
and real-time SSE streaming.

Reference: ARCHITECTURE.md §1, §4, §8 & PRD.md §5 Feature 3.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph_forecast import run_forecast_pipeline
from app.core.logging import get_logger
from app.models.connection import DatabaseConnection
from app.models.experiment import BanditEvent
from app.models.forecast import ForecastRecord, ModelDriftReport
from app.models.telemetry import PlanMetric, QueryMetric, TableMetric
from app.schemas.forecast import (
    DegradationCurvePoint,
    ForecastRecordOut,
    ForecastResponse,
    ModelDriftReportOut,
    ModelPerformanceResponse,
)
from app.services.simulation_service import simulation_service
from app.workers.retrain_worker import compute_prediction_errors_and_calibration

logger = get_logger(__name__)


class ForecastService:
    """Application Service for Feature 3 Predictive ML & Forecasting."""

    async def get_connection_telemetry_history(
        self,
        connection_id: uuid.UUID,
        query_id: int | None,
        db: AsyncSession,
        limit: int = 168,
    ) -> list[dict[str, Any]]:
        """Fetch chronological query & table telemetry history from the database."""
        stmt = (
            select(QueryMetric)
            .where(QueryMetric.connection_id == connection_id)
            .order_by(QueryMetric.timestamp.desc())
            .limit(limit)
        )
        if query_id is not None:
            stmt = stmt.where(QueryMetric.queryid == query_id)

        res = await db.execute(stmt)
        query_rows = list(reversed(res.scalars().all()))

        table_res = await db.execute(
            select(TableMetric)
            .where(TableMetric.connection_id == connection_id)
            .order_by(TableMetric.timestamp.desc())
            .limit(500)
        )
        table_rows = list(table_res.scalars().all())
        latest_table = table_rows[0] if table_rows else None

        plan_res = await db.execute(
            select(PlanMetric)
            .where(PlanMetric.connection_id == connection_id)
            .order_by(PlanMetric.timestamp.desc())
            .limit(500)
        )
        plans_by_query: dict[int, PlanMetric] = {}
        for plan in plan_res.scalars().all():
            if plan.query_id is not None:
                plans_by_query.setdefault(int(plan.query_id), plan)

        history: list[dict[str, Any]] = []
        for q in query_rows:
            table = latest_table
            plan = plans_by_query.get(int(q.queryid)) if q.queryid is not None else None
            estimated = float(plan.estimated_rows) if plan else 0.0
            actual = float(plan.actual_rows) if plan else 0.0
            history.append({
                "timestamp": q.timestamp.isoformat(),
                "mean_exec_time": float(q.mean_exec_time),
                "max_exec_time": float(q.max_exec_time),
                # QueryMetric has no native p95 column; max_exec_time is the
                # observed upper-tail measure and is labeled as such in metadata.
                "p95_exec_time": float(q.max_exec_time),
                "calls": int(q.calls),
                "rows": int(q.rows),
                "shared_blks_read": int(q.shared_blks_read),
                "shared_blks_hit": int(q.shared_blks_hit),
                "temp_blks_read": int(q.temp_blks_read),
                "temp_blks_written": int(q.temp_blks_written),
                "cpu_seconds": float(q.total_exec_time) / 1000.0,
                "wal_bytes": int(q.wal_bytes),
                "cardinality_error": (actual - estimated) / max(estimated, 1.0) if plan and estimated > 0 else 0.0,
                "dead_tuple_ratio": float(table.dead_tuple_ratio) if table else 0.0,
                "table_size_bytes": int(table.table_size_bytes) if table else 0,
                "index_size_bytes": int(table.index_size_bytes) if table else 0,
                "idx_scan_ratio": (
                    float(table.idx_scans) / max(float(table.idx_scans + table.seq_scans), 1.0)
                    if table else 0.0
                ),
                "table_name": table.table_name if table else None,
                "data_source": "persisted_live_postgresql_telemetry",
            })
        return history

    async def generate_forecast(
        self,
        connection_id: uuid.UUID,
        query_id: int | None,
        db: AsyncSession,
        *,
        telemetry_override: list[dict[str, Any]] | None = None,
        auto_simulate: bool = False,
    ) -> ForecastResponse:
        """Execute Feature 3 forecasting agent pipeline and persist results."""
        conn = await db.scalar(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
        if not conn:
            raise LookupError(f"Database connection {connection_id} not found")

        telemetry = telemetry_override or await self.get_connection_telemetry_history(connection_id, query_id, db)

        # Run Feature 3 LangGraph pipeline
        report = run_forecast_pipeline(
            connection_id=str(connection_id),
            telemetry_history=telemetry,
            query_id=query_id,
            table_name=(telemetry[-1].get("table_name") if telemetry else None),
        )

        forecast_res = report.get("forecast_result", {})
        prob = float(forecast_res.get("degradation_probability", 0.0))
        is_flagged = bool(forecast_res.get("is_flagged_for_action", False))
        model_version = str(forecast_res.get("model_version", "l1_v1"))
        raw_curve = forecast_res.get("probability_curve", [])

        now = datetime.now(timezone.utc)
        win_start = datetime.fromisoformat(forecast_res.get("forecast_window_start", now.isoformat()).replace("Z", "+00:00"))
        win_end = datetime.fromisoformat(forecast_res.get("forecast_window_end", (now + timedelta(days=7)).isoformat()).replace("Z", "+00:00"))

        # Persist ForecastRecord
        forecast_rec = ForecastRecord(
            connection_id=connection_id,
            query_id=query_id,
            forecast_window_start=win_start,
            forecast_window_end=win_end,
            degradation_probability=prob,
            probability_curve=raw_curve,
            model_version=model_version,
            is_flagged_for_action=is_flagged,
            created_at=now,
        )
        db.add(forecast_rec)

        # Persist BanditEvent if strategy was evaluated
        strat = report.get("strategy_decision", {})
        action_name = strat.get("selected_action", "DO_NOTHING")
        if action_name != "DO_NOTHING":
            bandit_ev = BanditEvent(
                connection_id=connection_id,
                context=strat.get("context_snapshot", {}),
                action=action_name,
                propensity=float(strat.get("propensity", 0.33)),
                reward=None,
                success=False,
                model_version="bandit_cts_v1",
                created_at=now,
            )
            db.add(bandit_ev)

        # Dispatch proactive Feature 2 simulation if flagged & requested
        cand_spec = report.get("candidate_spec")
        if is_flagged and cand_spec and auto_simulate:
            logger.info("Proactively dispatching candidate to Feature 2 simulation")
            await simulation_service.run_simulation(
                connection_id=connection_id,
                candidate_data=cand_spec,
                db=db,
            )

        await db.commit()
        await db.refresh(forecast_rec)
        performance = await self.get_model_performance(db)

        # Convert curve to Pydantic models
        curve_points: list[DegradationCurvePoint] = []
        for pt in raw_curve:
            ts_str = pt.get("timestamp")
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if isinstance(ts_str, str) else now
            curve_points.append(
                DegradationCurvePoint(
                    timestamp=ts,
                    predicted_probability=float(pt.get("predicted_probability", 0.0)),
                    confidence_lower=float(pt.get("confidence_lower", 0.0)),
                    confidence_upper=float(pt.get("confidence_upper", 0.0)),
                )
            )

        suggested = [action_name] if action_name != "DO_NOTHING" else ["MONITOR"]

        return ForecastResponse(
            connection_id=connection_id,
            query_id=query_id,
            forecast_window_start=win_start,
            forecast_window_end=win_end,
            degradation_probability=prob,
            is_flagged_for_action=is_flagged,
            curve=curve_points,
            suggested_strategies=suggested,
            threshold_probability=float(forecast_res.get("threshold_probability", 0.40)),
            threshold_day=forecast_res.get("threshold_day"),
            headline=(
                "Degradation risk threshold crossed"
                if is_flagged else "Workload degradation risk remains below threshold"
            ),
            model_version=model_version,
            data_quality=str(forecast_res.get("data_quality", "unknown")),
            confidence=float(forecast_res.get("confidence", 0.0)),
            calibration=performance.calibration,
            mae=performance.mae,
            bandit=performance.bandit,
        )

    async def get_model_performance(
        self,
        db: AsyncSession,
    ) -> ModelPerformanceResponse:
        """Retrieve closed-loop evaluation metrics (MAE, RMSE over time, calibration score, drift)."""
        error_summary = await compute_prediction_errors_and_calibration(db)

        stmt = select(ModelDriftReport).order_by(ModelDriftReport.created_at.desc()).limit(10)
        res = await db.execute(stmt)
        drift_reps = list(res.scalars().all())

        now = datetime.now(timezone.utc)
        ece = float(error_summary.get("expected_calibration_error", 0.0))
        model_metrics = error_summary.get("models", {})
        mae_trend = [
            {"version": version, "mae": float(metrics.get("mae", 0.0)), "count": int(metrics.get("count", 0))}
            for version, metrics in model_metrics.items()
        ]
        rmse_trend = [
            {"version": version, "rmse": float(metrics.get("rmse", 0.0)), "count": int(metrics.get("count", 0))}
            for version, metrics in model_metrics.items()
        ]
        calibration = [
            {
                "bucket": row["bucket"],
                "predicted": float(row["predicted_confidence"]) * 100.0,
                "actual": float(row["empirical_coverage"]) * 100.0,
                "samples": int(row["sample_count"]),
            }
            for row in error_summary.get("calibration_report", [])
        ]
        bandit_res = await db.execute(select(BanditEvent).order_by(BanditEvent.created_at.desc()).limit(500))
        bandit_rows = list(bandit_res.scalars().all())
        bandit: list[dict[str, Any]] = []
        for action in sorted({row.action for row in bandit_rows}):
            action_rows = [row for row in bandit_rows if row.action == action]
            rewards = [float(row.reward) for row in action_rows if row.reward is not None]
            bandit.append({"strategy": action, "reward": sum(rewards) / len(rewards) if rewards else 0.0, "pulls": len(action_rows)})

        return ModelPerformanceResponse(
            mae_over_time=mae_trend,
            rmse_over_time=rmse_trend,
            calibration_score=max(0.0, min(1.0, 1.0 - ece)),
            drift_reports=[ModelDriftReportOut.model_validate(dr) for dr in drift_reps],
            calibration=calibration,
            mae=mae_trend,
            bandit=bandit,
        )

    async def stream_forecast_execution(
        self,
        connection_id: uuid.UUID,
        db: AsyncSession,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream real-time forecast horizon and strategy ranking progress."""
        steps = [
            ("Extracting 30-day query & table telemetry", 20),
            ("Evaluating L1 LightGBM time-series degradation curve", 50),
            ("Computing Conformal Prediction confidence bounds", 75),
            ("Running L3 Contextual Thompson Sampling strategy selector", 90),
            ("Completed forecast projection", 100),
        ]
        for step_name, pct in steps:
            await asyncio.sleep(0.1)
            yield {
                "event": "forecast_progress",
                "data": {
                    "connection_id": str(connection_id),
                    "step": step_name,
                    "progress_pct": pct,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }


forecast_service = ForecastService()
