import pytest

from app.tools.pg_introspection import (
    _plan_features,
    _validate_read_query,
    build_lock_graph,
    calculate_cardinality_error,
    compare_plan,
)


def test_plan_features_extracts_nested_plan_metrics():
    plan = [{
        "Plan": {
            "Node Type": "Hash Join",
            "Plan Rows": 10,
            "Actual Rows": 12,
            "Total Cost": 42.5,
            "Actual Total Time": 3.25,
            "Shared Hit Blocks": 8,
            "Shared Read Blocks": 2,
            "Plans": [{
                "Node Type": "Seq Scan",
                "Plan Rows": 100,
                "Actual Rows": 120,
                "Shared Hit Blocks": 4,
                "Shared Read Blocks": 1,
            }],
        }
    }]

    result = _plan_features(plan)

    assert result["node_types"] == ["Hash Join", "Seq Scan"]
    assert result["join_types"] == ["Hash Join"]
    assert result["estimated_rows"] == 110
    assert result["actual_rows"] == 132
    assert result["buffer_hits"] == 12
    assert result["buffer_reads"] == 3


@pytest.mark.parametrize("query", [
    "UPDATE users SET name = 'x'",
    "DELETE FROM users",
    "SELECT 1; SELECT 2",
    "CREATE INDEX idx ON users(id)",
])
def test_explain_rejects_non_read_queries(query):
    with pytest.raises(ValueError):
        _validate_read_query(query)


def test_explain_accepts_select_and_with_queries():
    assert _validate_read_query(" SELECT * FROM users ") == "SELECT * FROM users"
    assert _validate_read_query("WITH rows AS (SELECT 1) SELECT * FROM rows").startswith("WITH")


def test_cardinality_error_is_log_difference():
    assert calculate_cardinality_error(999, 999) == pytest.approx(0)
    assert calculate_cardinality_error(9, 99) == pytest.approx(2.302585)


def test_compare_plan_reports_flip_and_deltas():
    result = compare_plan(
        {"plan_hash": "old", "estimated_rows": 10, "actual_rows": 20, "actual_time": 5},
        {"plan_hash": "new", "estimated_rows": 30, "actual_rows": 50, "actual_time": 8},
    )
    assert result["plan_changed"] is True
    assert result["estimated_rows_delta"] == 20
    assert result["actual_time_delta"] == 3


def test_build_lock_graph_only_links_waiters_to_granted_holders():
    result = build_lock_graph([
        {"pid": 10, "relation": 123, "granted": True, "mode": "AccessShareLock"},
        {"pid": 20, "relation": 123, "granted": False, "mode": "AccessExclusiveLock"},
        {"pid": 30, "relation": 456, "granted": False, "mode": "RowExclusiveLock"},
    ])
    assert result == [{
        "blocking_pid": 10,
        "blocked_pid": 20,
        "relation": 123,
        "mode": "AccessExclusiveLock",
    }]
