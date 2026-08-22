import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import AuditLog, DatabaseConnection, ModelDriftReport, ModelPrediction, OptimizationExperiment, User
from app.workers.retrain_worker import (
    compute_feature_drift_score,
    compute_prediction_errors_and_calibration,
    detect_feature_and_prediction_drift,
    evaluate_model_promotion,
    run_retrain_cycle,
)


@pytest_asyncio.fixture
async def retrain_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_compute_prediction_errors_and_calibration(retrain_db):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    async with retrain_db() as db:
        user = User(id=user_id, email="retrain@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="Retrain DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="rdb",
            username="postgres",
            is_active=True,
        )
        db.add_all([user, conn])
        await db.commit()

        # Seed 10 experiments with predictions across confidence spectrum
        now = datetime.now(timezone.utc)
        for i in range(10):
            exp = OptimizationExperiment(
                connection_id=connection_id,
                timestamp=now,
                strategy="CREATE_INDEX",
                candidate_sql="CREATE INDEX CONCURRENTLY idx_test ON test(col)",
                baseline_p95=100.0,
                candidate_p95=60.0 + i * 2,  # actual delta = -40 to -22
                predicted_latency_delta=-35.0,
                policy_verdict="VERIFIED",
                success=True,
                status="DEPLOYED",
            )
            db.add(exp)
            await db.flush()

            pred = ModelPrediction(
                experiment_id=exp.id,
                model_version="v1",
                prediction=-35.0,
                lower_bound=-50.0,
                upper_bound=-20.0,
                confidence=0.1 + (i * 0.09),  # spread across 5 buckets
                created_at=now,
            )
            db.add(pred)

        await db.commit()

        # Compute errors and calibration
        res = await compute_prediction_errors_and_calibration(db)

        assert res["total_labeled"] == 10
        assert res["mae"] > 0.0
        assert res["rmse"] > 0.0
        assert len(res["calibration_report"]) == 5
        assert "expected_calibration_error" in res

        # Verify DB updated
        reloaded_pred = await db.scalar(select(ModelPrediction).limit(1))
        assert reloaded_pred.actual is not None
        assert reloaded_pred.absolute_error is not None


def test_compute_feature_drift_score():
    # Identical distributions -> low drift score
    ref = [10.0, 12.0, 11.0, 10.5, 11.5, 12.5, 10.0]
    curr_same = [10.2, 11.8, 11.1, 10.4, 11.6, 12.4, 10.1]
    score_low = compute_feature_drift_score(ref, curr_same)
    assert score_low < 0.35

    # Strongly shifted distribution -> high drift score
    curr_shifted = [50.0, 60.0, 55.0, 52.0, 58.0, 62.0, 51.0]
    score_high = compute_feature_drift_score(ref, curr_shifted)
    assert score_high >= 0.80


@pytest.mark.asyncio
async def test_detect_feature_and_prediction_drift(retrain_db):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    async with retrain_db() as db:
        user = User(id=user_id, email="drift@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="Drift DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="ddb",
            username="postgres",
            is_active=True,
        )
        db.add_all([user, conn])
        await db.commit()

        now = datetime.now(timezone.utc)
        # Reference experiments (10 days ago)
        for i in range(8):
            exp_ref = OptimizationExperiment(
                connection_id=connection_id,
                timestamp=now - timedelta(days=10),
                strategy="CREATE_INDEX",
                candidate_sql="CREATE INDEX idx_ref ON t(c)",
                baseline_p95=50.0 + i,
                candidate_p95=30.0,
                predicted_latency_delta=-20.0,
                policy_verdict="VERIFIED",
                success=True,
                status="DEPLOYED",
            )
            db.add(exp_ref)

        # Current experiments (today - shifted)
        for i in range(8):
            exp_curr = OptimizationExperiment(
                connection_id=connection_id,
                timestamp=now - timedelta(hours=2),
                strategy="CREATE_INDEX",
                candidate_sql="CREATE INDEX idx_curr ON t(c)",
                baseline_p95=200.0 + i * 10,
                candidate_p95=100.0,
                predicted_latency_delta=-100.0,
                policy_verdict="VERIFIED",
                success=True,
                status="DEPLOYED",
            )
            db.add(exp_curr)

        await db.commit()

        # Run drift detection
        report = await detect_feature_and_prediction_drift(db, drift_threshold=0.30)
        assert report.id is not None
        assert report.dataset_drift_score > 0.0
        assert report.is_drift_detected is True


def test_evaluate_model_promotion():
    # 1. Candidate is 15% better -> Promoted
    promoted, reason = evaluate_model_promotion(current_mae=10.0, candidate_mae=8.5, min_improvement_ratio=0.03)
    assert promoted is True
    assert "improved by" in reason

    # 2. Candidate is worse -> Rejected
    rejected, reason_rej = evaluate_model_promotion(current_mae=10.0, candidate_mae=11.0, min_improvement_ratio=0.03)
    assert rejected is False
    assert "failed to improve" in reason_rej

    # 3. Candidate improved by only 1% (less than 3% requirement) -> Rejected
    rejected_small, _ = evaluate_model_promotion(current_mae=10.0, candidate_mae=9.9, min_improvement_ratio=0.03)
    assert rejected_small is False


@pytest.mark.asyncio
async def test_run_retrain_cycle(retrain_db, monkeypatch, tmp_path):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file:///{tmp_path.as_posix().lstrip('/')}")
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    async with retrain_db() as db:
        user = User(id=user_id, email="cycle@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="Cycle DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="cdb",
            username="postgres",
            is_active=True,
        )
        db.add_all([user, conn])
        await db.commit()

        # Run forced retrain cycle
        cycle_report = await run_retrain_cycle(db, force=True)

        assert cycle_report["status"] == "COMPLETED"
        assert cycle_report["retrain_triggered"] is True
        assert "l1_forecasting" in cycle_report["models_trained"]

        # Confirm AuditLog created
        audit = await db.scalar(select(AuditLog).where(AuditLog.action_type == "MODEL_RETRAIN_CYCLE"))
        assert audit is not None
