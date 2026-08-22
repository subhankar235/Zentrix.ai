"""pgbench workload generation for the fault laboratory."""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class WorkloadConfig:
    dsn: str
    clients: int = 4
    threads: int = 2
    duration_seconds: int = 30
    scale: int = 10
    extra_args: tuple[str, ...] = field(default_factory=tuple)


def pgbench_command(config: WorkloadConfig) -> list[str]:
    """Build a safe pgbench command without shell interpolation."""
    if config.clients < 1 or config.threads < 1 or config.duration_seconds < 1:
        raise ValueError("clients, threads, and duration_seconds must be positive")
    return [
        "pgbench",
        "-c", str(config.clients),
        "-j", str(config.threads),
        "-T", str(config.duration_seconds),
        *config.extra_args,
        config.dsn,
    ]


async def run_pgbench(config: WorkloadConfig) -> dict[str, object]:
    """Run pgbench and return reproducibility metadata and captured output."""
    command = pgbench_command(config)
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return {
        "command": shlex.join(command),
        "returncode": process.returncode,
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
        "success": process.returncode == 0,
    }


async def run_sql_workload(connection: object, statements: Sequence[str]) -> int:
    """Execute fixed lab statements when pgbench is unavailable in CI."""
    for statement in statements:
        await connection.execute(statement)
    return len(statements)
