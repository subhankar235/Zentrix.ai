"""Async Shadow Laboratory worker for safe simulation experiments.

Orchestrates ephemeral shadow database provisioning, baseline workload replay,
candidate optimization installation, candidate workload replay, and paired metric
collection per ARCHITECTURE.md §4, §8 & PRD.md §5 Feature 2.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import asyncpg
import numpy as np

from app.core.logging import get_logger
from app.tools.shadow_db_tool import (
    ShadowConfig,
    ShadowDatabase,
    install_candidate_optimization,
    is_docker_available,
    provision_shadow_db,
    teardown_shadow_db,
)

logger = get_logger(__name__)


@dataclass
class ReplayQuery:
    query: str
    args: Sequence[Any] = ()
    is_write: bool = False
    weight: int = 1


async def _execute_timed(
    connection: asyncpg.Connection,
    query: str,
    *args: Any,
) -> tuple[float, bool, str | None]:
    """Execute a single query and measure wall-clock latency in milliseconds."""
    start = time.perf_counter()
    try:
        await connection.fetch(query, *args)
        duration_ms = (time.perf_counter() - start) * 1000.0
        return duration_ms, True, None
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return duration_ms, False, str(exc)


async def replay_workload(
    connection: asyncpg.Connection,
    workload: Sequence[ReplayQuery | Mapping[str, Any] | str],
    *,
    iterations: int = 1,
) -> dict[str, Any]:
    """Replay a sequence of queries against a database connection and capture latency."""
    latencies: list[float] = []
    read_latencies: list[float] = []
    write_latencies: list[float] = []
    errors: list[str] = []

    for _ in range(max(1, iterations)):
        for item in workload:
            if isinstance(item, str):
                q, args, is_write = item, (), False
            elif isinstance(item, ReplayQuery):
                q, args, is_write = item.query, item.args, item.is_write
            elif isinstance(item, Mapping):
                q = item.get("query", "")
                args = item.get("args", item.get("parameters", ()))
                is_write = bool(item.get("is_write", False))
            else:
                continue

            lat, success, err = await _execute_timed(connection, q, *args)
            if success:
                latencies.append(lat)
                if is_write:
                    write_latencies.append(lat)
                else:
                    read_latencies.append(lat)
            else:
                errors.append(err or "Unknown query error")

    if not latencies:
        return {
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "mean_ms": 0.0,
            "sample_count": 0,
            "latencies": [],
            "write_mean_ms": 0.0,
            "error_rate": 1.0 if errors else 0.0,
            "errors": errors,
        }

    arr = np.asarray(latencies, dtype=np.float64)
    return {
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
        "mean_ms": float(np.mean(arr)),
        "sample_count": len(arr),
        "latencies": latencies,
        "write_mean_ms": float(np.mean(write_latencies)) if write_latencies else 0.0,
        "error_rate": len(errors) / max(len(latencies) + len(errors), 1),
        "errors": errors,
    }


class ShadowLabWorker:
    """Worker managing paired simulation runs against shadow or test databases."""

    async def run_simulation_experiment(
        self,
        target_connection: asyncpg.Connection,
        candidate_sql: str,
        workload: Sequence[ReplayQuery | Mapping[str, Any] | str],
        *,
        iterations: int = 1,
    ) -> dict[str, Any]:
        """Execute paired baseline vs candidate simulation on a connection."""
        # 1. Baseline workload replay
        baseline_metrics = await replay_workload(target_connection, workload, iterations=iterations)

        # 2. Install candidate optimization
        install_res = await install_candidate_optimization(target_connection, candidate_sql)
        if not install_res["success"]:
            return {
                "status": "FAILED",
                "candidate_sql": candidate_sql,
                "error": install_res["error"],
                "baseline_metrics": baseline_metrics,
                "candidate_metrics": None,
            }

        # 3. Candidate workload replay
        candidate_metrics = await replay_workload(target_connection, workload, iterations=iterations)

        # 4. Paired delta calculation
        base_lats = baseline_metrics["latencies"]
        cand_lats = candidate_metrics["latencies"]
        paired_count = min(len(base_lats), len(cand_lats))

        regressions = sum(1 for i in range(paired_count) if cand_lats[i] > base_lats[i])
        regression_rate = regressions / max(paired_count, 1)

        base_p95 = baseline_metrics["p95_ms"]
        cand_p95 = candidate_metrics["p95_ms"]
        p95_improvement = (base_p95 - cand_p95) / max(base_p95, 1e-6) if base_p95 > 0 else 0.0

        base_write = baseline_metrics["write_mean_ms"]
        cand_write = candidate_metrics["write_mean_ms"]
        write_increase = (
            (cand_write - base_write) / max(base_write, 1e-6)
            if base_write > 0 and cand_write > 0
            else 0.0
        )

        return {
            "status": "COMPLETED",
            "candidate_sql": candidate_sql,
            "install_duration_ms": install_res["duration_ms"],
            "sample_size": paired_count,
            "baseline_p50": baseline_metrics["p50_ms"],
            "baseline_p95": base_p95,
            "baseline_p99": baseline_metrics["p99_ms"],
            "candidate_p50": candidate_metrics["p50_ms"],
            "candidate_p95": cand_p95,
            "candidate_p99": candidate_metrics["p99_ms"],
            "p95_improvement_ratio": float(p95_improvement),
            "regression_rate": float(regression_rate),
            "write_latency_increase_ratio": float(max(0.0, write_increase)),
            "storage_increase_ratio": 0.05,  # Estimated index size ratio
            "baseline_metrics": baseline_metrics,
            "candidate_metrics": candidate_metrics,
        }

    async def run_ephemeral_experiment(
        self,
        candidate_sql: str,
        workload: Sequence[ReplayQuery | Mapping[str, Any] | str],
        config: ShadowConfig | None = None,
        *,
        iterations: int = 1,
    ) -> dict[str, Any]:
        """Full lifecycle: spin up shadow Docker container, run simulation, tear down."""
        shadow_instance: ShadowDatabase | None = None
        try:
            shadow_instance = await provision_shadow_db(config)
            conn = await shadow_instance.connect()
            try:
                result = await self.run_simulation_experiment(
                    conn, candidate_sql, workload, iterations=iterations
                )
                result["container_id"] = shadow_instance.container_id
                return result
            finally:
                await conn.close()
        finally:
            if shadow_instance:
                await teardown_shadow_db(shadow_instance.container_id)


shadow_lab_worker = ShadowLabWorker()
