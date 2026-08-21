"""Ground-truth record and JSONL dataset writer for fault-lab runs."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GroundTruthRecord:
    """One labeled experiment in the format consumed by RCA training."""

    scenario: str
    labels: list[str]
    telemetry: list[dict[str, Any]]
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=_utc_now)
    ended_at: str | None = None
    workload: dict[str, Any] = field(default_factory=dict)
    fault_parameters: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    schema_version: str = "fault-lab.v1"

    def finish(self, *, success: bool = True) -> None:
        self.ended_at = _utc_now()
        self.success = success

    def to_dict(self) -> dict[str, Any]:
        """Serialize a JSON-safe record while retaining trainer labels."""
        return asdict(self)


class GroundTruthRecorder:
    """Append records to JSONL or write a complete deterministic dataset."""

    def __init__(self, dataset_path: str | Path) -> None:
        self.dataset_path = Path(dataset_path)

    def record(
        self,
        *,
        scenario: str,
        labels: Sequence[str],
        telemetry: Sequence[Mapping[str, Any]],
        workload: Mapping[str, Any] | None = None,
        fault_parameters: Mapping[str, Any] | None = None,
        success: bool = True,
    ) -> GroundTruthRecord:
        record = GroundTruthRecord(
            scenario=scenario,
            labels=list(labels),
            telemetry=[dict(row) for row in telemetry],
            workload=dict(workload or {}),
            fault_parameters=dict(fault_parameters or {}),
            success=success,
        )
        record.finish(success=success)
        self.append(record)
        return record

    def append(self, record: GroundTruthRecord) -> None:
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        with self.dataset_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record.to_dict(), sort_keys=True, default=str) + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not self.dataset_path.exists():
            return []
        with self.dataset_path.open(encoding="utf-8") as stream:
            return [json.loads(line) for line in stream if line.strip()]


def flatten_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Expand each labeled record into RCA trainer rows."""
    rows: list[dict[str, Any]] = []
    for record in records:
        for telemetry in record.get("telemetry", []):
            rows.append({**telemetry, "labels": list(record.get("labels", [])), "experiment_id": record.get("experiment_id")})
    return rows


def load_training_rows(dataset_path: str | Path) -> list[dict[str, Any]]:
    recorder = GroundTruthRecorder(dataset_path)
    return flatten_records(recorder.read())
