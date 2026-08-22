from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.telemetry import PlanMetric, QueryMetric, TableMetric
from app.workers import telemetry_collector


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *args):
        return False


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return FakeAcquire(self.connection)


class FakeSession:
    def __init__(self):
        self.items = []

    def add_all(self, items):
        self.items.extend(items)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_collect_connection_normalizes_and_persists_all_metric_types(monkeypatch):
    connection_id = uuid4()
    captured = datetime.now(timezone.utc)
    query_rows = [{
        "db_id": 1,
        "userid": 10,
        "queryid": 99,
        "query": "SELECT count(*) FROM orders",
        "calls": 3,
        "total_exec_time": 12.5,
        "mean_exec_time": 4.16,
        "min_exec_time": 2,
        "max_exec_time": 6,
        "rows": 3,
        "shared_blks_hit": 10,
        "shared_blks_read": 2,
    }]
    table_rows = [{
        "schemaname": "public",
        "relname": "orders",
        "n_live_tup": 100,
        "n_dead_tup": 25,
        "table_size": 4096,
        "index_size": 1024,
        "seq_scan": 4,
        "seq_tup_read": 100,
        "idx_scan": 8,
        "idx_tup_fetch": 80,
        "n_tup_ins": 20,
        "n_tup_upd": 5,
        "n_tup_del": 1,
    }]

    async def query_metrics(_connection):
        return query_rows

    async def table_stats(_connection):
        return table_rows

    async def query_plan(_connection, _query):
        return {
            "node_types": ["Aggregate", "Seq Scan"],
            "join_types": [],
            "estimated_rows": 1,
            "actual_rows": 1,
            "estimated_cost": 10,
            "actual_time": 2,
            "buffer_hits": 5,
            "buffer_reads": 1,
            "parallel_workers": 0,
        }

    monkeypatch.setattr(telemetry_collector.pg_introspection, "get_query_metrics", query_metrics)
    monkeypatch.setattr(telemetry_collector.pg_introspection, "get_table_stats", table_stats)
    monkeypatch.setattr(telemetry_collector.pg_introspection, "get_query_plan", query_plan)

    session = FakeSession()
    previous = {("public", "orders"): {"n_tup_ins": 10, "n_tup_upd": 3, "n_tup_del": 0}}
    counts = await telemetry_collector.collect_connection_telemetry(
        connection_id,
        FakePool(object()),
        session,
        previous_tables=previous,
        previous_captured_at=captured,
    )

    assert counts == {"queries": 1, "tables": 1, "plans": 1}
    assert isinstance(session.items[0], QueryMetric)
    assert isinstance(session.items[1], TableMetric)
    assert isinstance(session.items[2], PlanMetric)
    assert session.items[0].query_hash
    assert session.items[1].dead_tuple_ratio == pytest.approx(0.2)
    assert session.items[2].query_metrics_id == session.items[0].id


def test_plan_eligibility_rejects_parameterized_or_multi_statement_queries():
    assert telemetry_collector._is_plan_eligible("SELECT 1")
    assert not telemetry_collector._is_plan_eligible("SELECT * FROM orders WHERE id = $1")
    assert not telemetry_collector._is_plan_eligible("SELECT 1; SELECT 2")
