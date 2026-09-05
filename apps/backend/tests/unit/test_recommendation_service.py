from app.services.recommendation_service import _index_candidates, _query_parts, _quoted_identifier


def test_query_parts_extracts_filter_and_order_columns_without_guessing_values():
    result = _query_parts(
        "SELECT id FROM orders WHERE customer_id = 42 AND state = 'open' ORDER BY created_at DESC"
    )

    assert result == ("orders", ["customer_id", "state"], ["created_at"])


def test_query_parts_rejects_parameterized_or_multi_statement_queries():
    assert _query_parts("SELECT * FROM orders WHERE customer_id = $1") is None
    assert _query_parts("SELECT * FROM orders WHERE customer_id = 1; DROP TABLE orders") is None


def test_control_plane_tables_are_never_customer_remediation_targets():
    assert _quoted_identifier("table_metrics") is None
    assert _query_parts("SELECT * FROM table_metrics WHERE connection_id = 1") is None


def test_query_parser_rejects_internal_postgres_observability_queries():
    assert _query_parts(
        "SELECT state FROM pg_catalog.pg_stat_activity WHERE state = 'active'"
    ) is None


def test_index_candidates_generate_rankable_safe_single_and_composite_options():
    candidates = _index_candidates(
        "SELECT id FROM orders WHERE customer_id = 42 ORDER BY created_at DESC"
    )

    assert [candidate["type"] for candidate in candidates] == ["INDEX", "INDEX"]
    assert candidates[0]["score"] > candidates[1]["score"]
    assert "customer_id, created_at" in candidates[0]["candidate_sql"]
    assert "DROP INDEX CONCURRENTLY" in candidates[0]["rollback_sql"]
    assert all(candidate["requires_hypopg"] for candidate in candidates)
