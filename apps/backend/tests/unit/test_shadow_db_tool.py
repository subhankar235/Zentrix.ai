import pytest

from app.tools.shadow_db_tool import (
    ShadowConfig,
    ShadowDatabase,
    ShadowProvisioningError,
    clone_schema_and_tables,
    install_candidate_optimization,
    is_docker_available,
    provision_shadow_db,
    teardown_shadow_db,
)
from app.workers.shadow_lab_worker import ReplayQuery, ShadowLabWorker, replay_workload


class MockAsyncpgConnection:
    def __init__(self):
        self.executed_statements = []
        self.schema_queries = []
        self.tables = {
            "users": [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"},
            ]
        }

    async def execute(self, statement, *args):
        self.executed_statements.append((statement, args))
        return "OK"

    async def fetch(self, query, *args):
        if "information_schema.columns" in query:
            return [
                {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
                {"column_name": "name", "data_type": "text", "is_nullable": "YES"},
                {"column_name": "email", "data_type": "text", "is_nullable": "YES"},
            ]
        if "SELECT * FROM" in query:
            return [{"id": 1, "name": "Alice", "email": "alice@example.com"}]
        return [{"result": 1}]

    async def fetchval(self, query, *args):
        return 1

    async def close(self):
        pass


def test_shadow_config_defaults():
    cfg = ShadowConfig()
    assert cfg.postgres_user == "postgres"
    assert cfg.postgres_password == "shadowpass"
    assert cfg.postgres_db == "shadow_test"
    assert cfg.memory_limit == "2g"
    assert cfg.mode == "full_clone"


@pytest.mark.asyncio
async def test_install_candidate_optimization():
    conn = MockAsyncpgConnection()
    res = await install_candidate_optimization(
        conn, "CREATE INDEX idx_users_email ON users(email)"
    )
    assert res["success"] is True
    assert res["candidate_sql"] == "CREATE INDEX idx_users_email ON users(email)"
    assert res["duration_ms"] >= 0
    assert len(conn.executed_statements) == 1


@pytest.mark.asyncio
async def test_clone_schema_and_tables():
    src_conn = MockAsyncpgConnection()
    tgt_conn = MockAsyncpgConnection()

    res = await clone_schema_and_tables(src_conn, tgt_conn, ["users"], sample_limit=10)
    assert res["status"] == "CLONED"
    assert res["tables"] == ["users"]
    assert any("CREATE TABLE IF NOT EXISTS" in stmt[0] for stmt in tgt_conn.executed_statements)
    assert any("INSERT INTO" in stmt[0] for stmt in tgt_conn.executed_statements)


@pytest.mark.asyncio
async def test_shadow_lab_worker_paired_simulation():
    conn = MockAsyncpgConnection()
    worker = ShadowLabWorker()

    workload = [
        ReplayQuery(query="SELECT * FROM users WHERE email = 'alice@example.com'"),
        {"query": "SELECT * FROM users WHERE id = 1"},
    ]

    res = await worker.run_simulation_experiment(
        conn,
        "CREATE INDEX idx_users_email ON users(email)",
        workload,
        iterations=2,
    )

    assert res["status"] == "COMPLETED"
    assert res["candidate_sql"] == "CREATE INDEX idx_users_email ON users(email)"
    assert res["sample_size"] == 4
    assert "baseline_p95" in res
    assert "candidate_p95" in res
    assert 0 <= res["regression_rate"] <= 1.0


@pytest.mark.asyncio
async def test_provision_shadow_db_fails_gracefully_when_docker_unavailable(monkeypatch):
    monkeypatch.setattr("app.tools.shadow_db_tool.is_docker_available", lambda: False)
    with pytest.raises(ShadowProvisioningError, match="Docker is not available"):
        await provision_shadow_db()
