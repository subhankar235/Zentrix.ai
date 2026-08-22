import pytest

from app.tools.hypopg_tool import (
    _extract_plan_cost_and_indexes,
    create_hypothetical_index,
    drop_hypothetical_index,
    evaluate_hypothetical_index,
    filter_candidates,
    list_hypothetical_indexes,
    reset_hypothetical_indexes,
    validate_index_statement,
)


class MockHypoConnection:
    def __init__(self):
        self.active_indexes = set()
        self.created_indexes = []
        self.dropped_indexes = []
        self.executed_statements = []
        self._next_id = 1000

    async def fetchrow(self, query, *args):
        if "pg_extension" in query:
            return (1,)
        if "hypopg_create_index" in query:
            stmt = args[0]
            self._next_id += 1
            idx_id = self._next_id
            self.created_indexes.append(stmt)
            self.active_indexes.add(idx_id)
            return (idx_id, f"hypo_idx_{idx_id}")
        if "hypopg_drop_index" in query:
            idx_id = args[0]
            self.dropped_indexes.append(idx_id)
            self.active_indexes.discard(idx_id)
            return (True,)
        return None

    async def execute(self, query, *args):
        self.executed_statements.append((query, args))
        if "hypopg_reset" in query:
            self.active_indexes.clear()
        return "OK"

    async def fetch(self, query, *args):
        if "hypopg_list_indexes" in query:
            return [
                {"indexrelid": idx_id, "indexname": f"hypo_idx_{idx_id}", "nspname": "public", "relname": "orders", "amname": "btree"}
                for idx_id in self.active_indexes
            ]
        if "EXPLAIN (FORMAT JSON)" in query:
            if self.active_indexes:
                # Candidate plan with active hypothetical index (lower cost)
                idx_id = next(iter(self.active_indexes))
                return [[{
                    "Plan": {
                        "Node Type": "Index Scan",
                        "Index Name": f"hypo_idx_{idx_id}",
                        "Total Cost": 15.5,
                        "Plan Rows": 10,
                    }
                }]]
            else:
                # Baseline plan without index (higher cost)
                return [[{
                    "Plan": {
                        "Node Type": "Seq Scan",
                        "Total Cost": 120.0,
                        "Plan Rows": 1000,
                    }
                }]]
        return []



def test_validate_index_statement():
    valid = validate_index_statement("CREATE INDEX idx_user ON users(email);")
    assert valid == "CREATE INDEX idx_user ON users(email)"

    valid_concurrent = validate_index_statement("CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users ON users(id, tenant_id)")
    assert "UNIQUE INDEX CONCURRENTLY" in valid_concurrent

    with pytest.raises(ValueError, match="Invalid CREATE INDEX statement"):
        validate_index_statement("SELECT * FROM users")


def test_extract_plan_cost_and_indexes():
    plan = [{
        "Plan": {
            "Total Cost": 45.2,
            "Index Name": "idx_a",
            "Plans": [{
                "Total Cost": 20.0,
                "Index Name": "idx_b",
            }]
        }
    }]
    cost, indexes = _extract_plan_cost_and_indexes(plan)
    assert cost == 45.2
    assert set(indexes) == {"idx_a", "idx_b"}


@pytest.mark.asyncio
async def test_hypopg_lifecycle_and_evaluation():
    conn = MockHypoConnection()
    res = await evaluate_hypothetical_index(
        conn,
        "SELECT * FROM orders WHERE user_id = 42",
        "CREATE INDEX idx_orders_user_id ON orders(user_id)",
    )

    assert res["signal_type"] == "PLANNER_COST_SIGNAL"
    assert res["is_verified_performance"] is False
    assert res["is_improvement"] is True
    assert res["baseline_cost"] == 120.0
    assert res["candidate_cost"] == 15.5
    assert res["cost_delta"] == pytest.approx(-104.5)
    assert res["cost_reduction_ratio"] > 0.85
    assert len(conn.dropped_indexes) == 1
    assert conn.dropped_indexes[0] == 1001


@pytest.mark.asyncio
async def test_filter_candidates_ranks_by_cost_reduction():
    conn = MockHypoConnection()
    candidates = [
        "CREATE INDEX idx_1 ON orders(user_id)",
        "CREATE INDEX idx_2 ON orders(created_at)",
    ]
    filtered = await filter_candidates(
        conn,
        "SELECT * FROM orders WHERE user_id = 42",
        candidates,
        top_k=5,
    )
    assert len(filtered) == 2
    assert filtered[0]["is_improvement"] is True
    assert filtered[0]["cost_reduction_ratio"] > 0
