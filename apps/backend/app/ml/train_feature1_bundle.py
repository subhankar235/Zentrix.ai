"""Generate and train the Feature 1 model bundle from the isolated Fault Lab.

This command is deliberately separate from live diagnosis. It may mutate only
the Dockerized Fault Lab database and never the user's monitored database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

from app.ml.rca_classifier.fault_lab.injector import FaultType, apply_fault, scenario
from app.tools import pg_introspection


DEFAULT_DSN = "postgresql://fault_lab:fault_lab_dev_password@localhost:5433/fault_lab"
LAB_TABLE = "fault_lab_orders"


async def _prepare_table(connection: asyncpg.Connection, table: str) -> None:
    await connection.execute(
        f"CREATE TABLE IF NOT EXISTS {table} (id BIGSERIAL PRIMARY KEY, customer_id BIGINT NOT NULL, amount NUMERIC NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    count = await connection.fetchval(f"SELECT count(*) FROM {table}")
    if not count:
        await connection.execute(
            f"INSERT INTO {table} (customer_id, amount) SELECT (g % 1000) + 1, (g % 100) + 1 FROM generate_series(1, 100000) AS g"
        )
    await connection.execute(f"CREATE INDEX IF NOT EXISTS {table}_customer_id_idx ON {table} (customer_id)")
    await connection.execute(f"ANALYZE {table}")


async def _snapshot(connection: asyncpg.Connection, table: str, query: str) -> dict[str, Any]:
    captured_at = datetime.now(timezone.utc)
    plan = await pg_introspection.get_explain_plan(connection, query)
    table_rows = await pg_introspection.get_table_stats(connection, table=table)
    table_row = table_rows[0] if table_rows else {}
    buffer_rows = await pg_introspection.get_buffer_stats(connection)
    buffer_row = next((row for row in buffer_rows if row.get("relname") == table), {})
    activity = await pg_introspection.get_pg_activity(connection)
    locks = await pg_introspection.get_pg_locks(connection)
    waiting = [
        row for row in activity
        if str(row.get("wait_event_type") or "").lower() == "lock"
        or row.get("pid") in {lock.get("pid") for lock in locks if lock.get("granted") is False}
    ]
    live = float(table_row.get("n_live_tup") or 0)
    dead = float(table_row.get("n_dead_tup") or 0)
    seq_scans = float(table_row.get("seq_scan") or 0)
    idx_scans = float(table_row.get("idx_scan") or 0)
    heap_reads = float(buffer_row.get("heap_blks_read") or 0)
    heap_hits = float(buffer_row.get("heap_blks_hit") or 0)
    return {
        "timestamp": captured_at.isoformat(),
        "query_hash": plan.get("query_hash"),
        "table_name": table,
        "estimated_rows": plan.get("estimated_rows"),
        "actual_rows": plan.get("actual_rows"),
        "estimated_cost": plan.get("estimated_cost"),
        "actual_time": plan.get("actual_time"),
        "execution_time": plan.get("actual_time"),
        "latency_p95": plan.get("actual_time"),
        "buffer_hits": plan.get("buffer_hits", heap_hits),
        "buffer_reads": plan.get("buffer_reads", heap_reads),
        "buffer_hit_ratio": heap_hits / max(heap_hits + heap_reads, 1.0),
        "dead_tuple_ratio": dead / max(live + dead, 1.0),
        "idx_scan_ratio": idx_scans / max(idx_scans + seq_scans, 1.0),
        "lock_wait_seconds": float(len(waiting)),
        "connection_count": len(activity),
        "temp_io": 0.0,
        "wal_rate": 0.0,
        "plan_flip": 0.0,
        "table_growth_rate": 0.0,
        "analyze_age": 0.0,
        "vacuum_age": 0.0,
    }


async def collect_dataset(dsn: str, baseline_rows: int = 30) -> list[dict[str, Any]]:
    connection = await asyncpg.connect(dsn)
    try:
        rows: list[dict[str, Any]] = []
        await _prepare_table(connection, LAB_TABLE)
        baseline_query = f"SELECT * FROM {LAB_TABLE} WHERE customer_id = 42"
        for _ in range(max(30, baseline_rows)):
            rows.append({**await _snapshot(connection, LAB_TABLE, baseline_query), "labels": ["UNKNOWN"]})

        scenarios = [
            FaultType.STALE_STATISTICS,
            FaultType.PLAN_FLIP,
            FaultType.CARDINALITY_MISESTIMATION,
            FaultType.VACUUM_LAG,
            FaultType.INDEX_MISSING,
            FaultType.INDEX_UNUSED,
            FaultType.IO_SATURATION,
            FaultType.BUFFER_PRESSURE,
        ]
        for fault_type in scenarios:
            table = f"fault_lab_{fault_type.value.lower()}"
            await _prepare_table(connection, table)
            fault = scenario(fault_type.value, table=table)
            await apply_fault(connection, fault)
            query = f"SELECT * FROM {table} WHERE customer_id = 42"
            rows.append({**await _snapshot(connection, table, query), "labels": list(fault.labels)})
        return rows
    finally:
        await connection.close()


def train_bundle(rows: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    from app.ml.anomaly.train import train as train_anomaly
    from app.ml.rca_classifier.train import train as train_rca
    from app.ml.temporal.features import build_windows
    from app.ml.temporal.train import train as train_temporal

    output_dir.mkdir(parents=True, exist_ok=True)
    anomaly_path = output_dir / "anomaly_model.joblib"
    rca_path = output_dir / "rca_model.joblib"
    temporal_path = output_dir / "temporal_model.pt"
    train_anomaly(rows, anomaly_path, contamination=0.2)
    train_rca(rows, rca_path)
    windows = build_windows(rows, window_size=30, stride=1)
    train_temporal(windows, temporal_path, epochs=10)
    manifest = {
        "source": "fault_lab",
        "status": "promoted",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "temporal_windows": int(len(windows)),
        "artifacts": {
            "anomaly": str(anomaly_path),
            "rca": str(rca_path),
            "temporal": str(temporal_path),
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.getenv("FAULT_LAB_DSN", DEFAULT_DSN))
    parser.add_argument("--output", default=os.getenv("FEATURE1_ARTIFACT_DIR", ".artifacts"))
    parser.add_argument("--dataset", default=None, help="Existing JSON dataset to train instead of collecting")
    parser.add_argument("--dataset-out", default=None, help="Write collected labeled rows to JSON")
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args()
    rows = json.loads(Path(args.dataset).read_text(encoding="utf-8")) if args.dataset else await collect_dataset(args.dsn)
    if args.dataset_out:
        dataset_path = Path(args.dataset_out)
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    if args.collect_only:
        print(json.dumps({"rows": len(rows), "dataset": args.dataset_out}, indent=2))
        return
    print(json.dumps(train_bundle(rows, Path(args.output)), indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
