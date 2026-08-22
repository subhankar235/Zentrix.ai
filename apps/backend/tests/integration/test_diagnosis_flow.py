import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.main import app
from app.db.base import Base
from app.models import DatabaseConnection, PlanMetric, QueryMetric, TableMetric, User
from app.services import diagnosis_service as diagnosis_module


@pytest_asyncio.fixture
async def diagnosis_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_diagnosis_service_persists_report_and_evidence_graph(diagnosis_db, monkeypatch):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    async with diagnosis_db() as db:
        db.add(User(id=user_id, email="diagnosis@example.com", hashed_password="hash", is_active=True))
        db.add(DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="Fixture DB",
            encrypted_connection_string="encrypted",
            host="localhost",
            port=5432,
            database_name="fixture",
            username="reader",
            is_active=True,
        ))
        query = QueryMetric(id=uuid.uuid4(), connection_id=connection_id, timestamp=now, query_hash="q1", mean_exec_time=100, max_exec_time=200, shared_blks_read=50)
        db.add_all([
            query,
            TableMetric(connection_id=connection_id, timestamp=now, table_name="orders", live_tuples=100, dead_tuples=50, dead_tuple_ratio=0.33),
        ])
        await db.flush()
        db.add(PlanMetric(connection_id=connection_id, query_metrics_id=query.id, timestamp=now, plan_hash="p1", estimated_rows=1, actual_rows=100, actual_time=200))
        await db.commit()

        monkeypatch.setattr(diagnosis_module, "run_agent_graph", lambda evidence, **_: {
            "title": "Fixture diagnosis",
            "primary_root_cause": "CARDINALITY_MISESTIMATION",
            "confidence": 0.88,
            "severity": "HIGH",
            "summary": "The plan underestimates rows.",
            "contributing_factors": [],
            "validation_plan": {"steps": ["re-run explain"]},
            "hypotheses": [{"agent": "PLANNER", "cause": "CARDINALITY_MISESTIMATION", "confidence": 0.88, "evidence": [{"claim": "row mismatch", "directness": 1.0}]}],
            "evidence": [{"metric": "cardinality_error", "value": 3.9, "directness": 1.0}],
        })

        diagnosis = await diagnosis_module.run_diagnosis(connection_id, db)
        assert diagnosis.primary_root_cause == "CARDINALITY_MISESTIMATION"
        assert len(diagnosis.nodes) == 3
        assert len(diagnosis.edges) == 2


@pytest.mark.asyncio
async def test_diagnosis_api_lists_and_returns_persisted_report(diagnosis_db, monkeypatch):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    async with diagnosis_db() as db:
        db.add(User(id=user_id, email="api-diagnosis@example.com", hashed_password="hash", is_active=True))
        db.add(DatabaseConnection(id=connection_id, user_id=user_id, name="API DB", encrypted_connection_string="encrypted", host="localhost", port=5432, database_name="fixture", username="reader", is_active=True))
        await db.commit()
        monkeypatch.setattr(diagnosis_module, "run_agent_graph", lambda evidence, **_: {
            "title": "Cold start diagnosis", "primary_root_cause": "UNKNOWN", "confidence": 0.0,
            "severity": "LOW", "summary": "UNKNOWN", "validation_plan": {}, "hypotheses": [], "evidence": [],
        })
        diagnosis = await diagnosis_module.run_diagnosis(connection_id, db)
        diagnosis_id = diagnosis.id

    async def override_db():
        async with diagnosis_db() as session:
            yield session

    async def override_user():
        return User(id=user_id, email="api-diagnosis@example.com", hashed_password="hash", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get(f"/api/v1/connections/{connection_id}/diagnoses")
            detail = await client.get(f"/api/v1/diagnoses/{diagnosis_id}")
        assert listed.status_code == 200
        assert listed.json()[0]["primary_root_cause"] == "UNKNOWN"
        assert detail.status_code == 200
        assert len(detail.json()["evidence_graph"]["nodes"]) == 1
    finally:
        app.dependency_overrides.clear()
