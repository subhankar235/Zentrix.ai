from app.agents.graph_diagnosis import run_diagnosis
from app.ml.diagnosis_models import ensure_feature1_models
from app.services.diagnosis_service import _lock_waiters


def test_normal_postgres_wait_events_are_not_lock_contention():
    activity = [
        {"pid": 10, "wait_event_type": "Client", "wait_event": "ClientRead"},
        {"pid": 11, "wait_event_type": "Activity", "wait_event": "AutoVacuumMain"},
    ]

    assert _lock_waiters(activity, []) == []


def test_ungranted_lock_is_counted_even_when_activity_has_no_wait_event():
    activity = [{"pid": 42, "wait_event_type": None, "wait_event": None}]
    locks = [{"pid": 42, "granted": False, "relation": 123}]

    assert _lock_waiters(activity, locks) == activity


def test_live_metrics_without_lock_wait_do_not_force_lock_diagnosis():
    report = run_diagnosis(
        {
            "metrics": {
                "query_count": 3,
                "lock_wait_count": 0,
                "lock_wait_seconds": 0,
            }
        }
    )

    assert report["primary_root_cause"] != "LOCK_CONTENTION"


def test_missing_model_artifacts_are_reported_without_bootstrap_data(tmp_path, monkeypatch):
    monkeypatch.setenv("ANOMALY_MODEL_PATH", str(tmp_path / "anomaly.joblib"))
    monkeypatch.setenv("RCA_MODEL_PATH", str(tmp_path / "rca.joblib"))
    monkeypatch.setenv("TEMPORAL_MODEL_PATH", str(tmp_path / "temporal.pt"))

    result = ensure_feature1_models()

    assert result["status"] == "missing_artifact"
    assert set(result["missing"]) == {"anomaly", "rca", "temporal"}
    assert list(tmp_path.iterdir()) == []


def test_seq_scan_ratio_alone_does_not_claim_missing_index():
    report = run_diagnosis({"metrics": {"seq_scan_ratio": 1.0}})

    assert report["primary_root_cause"] == "UNKNOWN"


def test_large_live_sequential_scan_has_query_specific_evidence():
    report = run_diagnosis(
        {
            "metrics": {},
            "plan_metrics": [
                {
                    "node_types": ["Seq Scan"],
                    "actual_rows": 2500,
                    "query_hash": "live-query",
                    "query_text": "SELECT * FROM orders WHERE customer_id = 42",
                    "table_name": "orders",
                }
            ],
        }
    )

    assert report["primary_root_cause"] == "INDEX_MISSING"
    assert report["evidence"][0]["table_name"] == "orders"


def test_live_snapshot_without_breaches_is_reported_as_observation():
    report = run_diagnosis(
        {
            "source": "live_postgresql",
            "query_metrics": [{"query_hash": "q1"}],
            "table_metrics": [{"table_name": "orders"}],
            "plan_metrics": [],
            "timeline": [{"event": "query_telemetry"}],
            "capture_errors": [],
            "plan_errors": [],
        }
    )

    assert report["primary_root_cause"] == "NO_ACTIVE_INCIDENT"
    assert report["status"] == "OBSERVED"


def test_live_snapshot_without_diagnostic_data_is_insufficient():
    report = run_diagnosis(
        {
            "source": "live_postgresql",
            "query_metrics": [],
            "table_metrics": [],
            "plan_metrics": [],
            "timeline": [],
            "capture_errors": [],
            "plan_errors": [],
        }
    )

    assert report["primary_root_cause"] == "INSUFFICIENT_EVIDENCE"
    assert report["status"] == "INSUFFICIENT_EVIDENCE"


def test_internal_provider_plan_failure_does_not_hide_live_snapshot():
    report = run_diagnosis(
        {
            "source": "live_postgresql",
            "query_metrics": [{"query_hash": "q1"}],
            "table_metrics": [{"table_name": "orders"}],
            "plan_metrics": [],
            "timeline": [{"event": "query_telemetry"}],
            "capture_errors": [],
            "plan_errors": [{"error": "relation neon.neon_perf_counters does not exist"}],
        }
    )

    assert report["primary_root_cause"] == "NO_ACTIVE_INCIDENT"
