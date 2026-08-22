import json

import pytest

from app.ml.rca_classifier.fault_lab.ground_truth_recorder import (
    GroundTruthRecorder,
    load_training_rows,
)
from app.ml.rca_classifier.fault_lab.injector import apply_fault, scenario
from app.ml.rca_classifier.fault_lab.workload_gen import WorkloadConfig, pgbench_command


class FakeConnection:
    def __init__(self):
        self.statements = []

    async def execute(self, statement, *args):
        self.statements.append((statement, args))


@pytest.mark.asyncio
async def test_fault_scenario_produces_labeled_training_record(tmp_path):
    connection = FakeConnection()
    fault = scenario("stale_statistics", table="fault_lab_orders")
    applied = await apply_fault(connection, fault)
    telemetry = [{
        "dead_tuple_ratio": 0.02,
        "analyze_age": 3600,
        "cardinality_error": 1.4,
        "latency_p95": 25,
    }]
    dataset = tmp_path / "faults.jsonl"
    record = GroundTruthRecorder(dataset).record(
        scenario=fault.name,
        labels=fault.labels,
        telemetry=telemetry,
        fault_parameters=fault.parameters,
        workload={"kind": "fixture", "statements": len(applied["statements"])},
    )

    payload = json.loads(dataset.read_text(encoding="utf-8").splitlines()[0])
    rows = load_training_rows(dataset)
    assert payload["schema_version"] == "fault-lab.v1"
    assert payload["experiment_id"] == record.experiment_id
    assert payload["labels"] == ["STALE_STATISTICS"]
    assert rows[0]["labels"] == ["STALE_STATISTICS"]
    assert len(connection.statements) == 2


def test_pgbench_command_is_explicit_and_reproducible():
    command = pgbench_command(WorkloadConfig(
        dsn="postgresql://fault_lab@localhost:5433/fault_lab",
        clients=2,
        threads=1,
        duration_seconds=5,
    ))
    assert command == [
        "pgbench", "-c", "2", "-j", "1", "-T", "5",
        "postgresql://fault_lab@localhost:5433/fault_lab",
    ]
