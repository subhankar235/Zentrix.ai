"""Train the anomaly detector from application-database telemetry.

This command intentionally consumes only collected PostgreSQL telemetry. The
RCA classifier and temporal/outcome models have separate laboratory datasets
and must not be trained from unlabeled production snapshots.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.ml.anomaly.train import train
from app.models.telemetry import QueryMetric


def _row(metric: QueryMetric) -> dict[str, float]:
    return {
        "timestamp": metric.timestamp.isoformat(),
        "calls": metric.calls,
        "execution_time": metric.mean_exec_time,
        "latency_p50": metric.mean_exec_time,
        "latency_p95": metric.max_exec_time,
        "buffer_hits": metric.shared_blks_hit,
        "buffer_reads": metric.shared_blks_read,
        "temp_blks_read": metric.temp_blks_read,
        "temp_blks_written": metric.temp_blks_written,
        "wal_rate": metric.wal_bytes,
        "planning_time": metric.planning_time,
    }


async def collect_rows(limit: int | None = None) -> list[dict[str, float]]:
    async with async_session_factory() as session:
        statement = (
            select(QueryMetric)
            .where(QueryMetric.capture_source == "live_postgresql")
            .order_by(QueryMetric.timestamp.asc())
        )
        if limit:
            statement = statement.limit(limit)
        result = await session.execute(statement)
        return [_row(metric) for metric in result.scalars().all()]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=None, help="Model artifact path")
    parser.add_argument("--limit", type=int, default=None, help="Optional telemetry row limit")
    args = parser.parse_args()

    rows = await collect_rows(args.limit)
    output = args.output or get_settings().ANOMALY_MODEL_PATH
    result = train(rows, Path(output))
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
