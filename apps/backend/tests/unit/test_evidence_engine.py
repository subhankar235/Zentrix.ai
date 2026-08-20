from datetime import datetime, timezone

import pytest

from app.services.evidence_engine import (
    build_lock_graph,
    calculate_cardinality_error,
    calculate_vacuum_metrics,
    compute_vacuum_metrics,
    detect_plan_flip,
    diff_plans,
)


def test_cardinality_error_uses_log1p_difference():
    assert calculate_cardinality_error(999, 999) == pytest.approx(0)
    assert calculate_cardinality_error(9, 99) == pytest.approx(2.302585)


def test_plan_diff_detects_plan_flip_and_preserves_deltas():
    result = diff_plans(
        {"plan_hash": "old", "estimated_rows": 10, "actual_rows": 20, "actual_time": 5},
        {"plan_hash": "new", "estimated_rows": 30, "actual_rows": 50, "actual_time": 8},
    )

    assert result["plan_flip"] is True
    assert result["plan_changed"] is True
    assert result["estimated_rows_delta"] == 20
    assert result["actual_time_delta"] == 3
    assert detect_plan_flip({"plan_hash": "same"}, {"plan_hash": "same"}) is False


def test_lock_graph_links_waiters_to_granted_holders():
    assert build_lock_graph([
        {"pid": 10, "relation": 123, "granted": True, "mode": "AccessShareLock"},
        {"pid": 20, "relation": 123, "granted": False, "mode": "AccessExclusiveLock"},
        {"pid": 30, "relation": 456, "granted": False, "mode": "RowExclusiveLock"},
    ]) == [{
        "blocking_pid": 10,
        "blocked_pid": 20,
        "relation": 123,
        "mode": "AccessExclusiveLock",
    }]


def test_vacuum_metrics_calculate_ages_bloat_and_growth():
    now = datetime(2025, 1, 1, 1, 0, tzinfo=timezone.utc)
    previous = {
        "timestamp": datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
        "live_tuples": 100,
        "dead_tuples": 10,
        "table_size_bytes": 1_000,
    }
    current = {
        **previous,
        "timestamp": now,
        "live_tuples": 120,
        "dead_tuples": 30,
        "table_size_bytes": 1_600,
        "last_autovacuum": datetime(2024, 12, 31, 23, 30, tzinfo=timezone.utc),
        "last_autoanalyze": datetime(2024, 12, 31, 22, 0, tzinfo=timezone.utc),
    }

    result = calculate_vacuum_metrics(current, previous, now=now)

    assert result["dead_tuple_ratio"] == pytest.approx(0.2)
    assert result["vacuum_age"] == pytest.approx(5_400)
    assert result["analyze_age"] == pytest.approx(10_800)
    assert result["autovacuum_lag"] == pytest.approx(5_400)
    assert result["table_size_bytes_growth_rate"] == pytest.approx(600 / 3600)
    assert result["table_growth_rate"] == pytest.approx(600 / 3600)


def test_compute_vacuum_metrics_compares_rows_per_table():
    rows = [
        {"timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc), "table_name": "orders", "n_live_tup": 10, "n_dead_tup": 0},
        {"timestamp": datetime(2025, 1, 1, 1, tzinfo=timezone.utc), "table_name": "orders", "n_live_tup": 20, "n_dead_tup": 5},
    ]

    result = compute_vacuum_metrics(rows, now=datetime(2025, 1, 1, 1, tzinfo=timezone.utc))

    assert result[0]["dead_tuple_ratio"] == 0
    assert result[0]["table_growth_rate"] is None
    assert result[1]["dead_tuple_ratio"] == pytest.approx(5 / 25)
    assert result[1]["row_growth_rate"] == pytest.approx(10 / 3600)
