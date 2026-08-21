"""Ephemeral Shadow Database management tool.

Clones monitored customer PostgreSQL databases into isolated ephemeral
Docker containers using pg_dump/pg_restore or schema/data copies to enable
safe, paired workload replay and statistical verification without risk to
production.

Reference: ARCHITECTURE.md §4, §8 & PRD.md §5 Feature 2.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShadowProvisioningError(RuntimeError):
    """Raised when an ephemeral shadow container cannot be provisioned."""


@dataclass
class ShadowConfig:
    image: str = field(default_factory=lambda: get_settings().SHADOW_DB_IMAGE)
    container_prefix: str = "zentrix-shadow"
    postgres_user: str = "postgres"
    postgres_password: str = "shadowpass"
    postgres_db: str = "shadow_test"
    port: int | None = None
    memory_limit: str = "2g"
    startup_timeout_seconds: float = 30.0
    mode: str = "full_clone"  # 'full_clone', 'schema_only', 'sampled'


@dataclass
class ShadowDatabase:
    container_id: str
    container_name: str
    port: int
    dsn: str
    is_ready: bool = False

    async def connect(self) -> asyncpg.Connection:
        """Establish a direct asyncpg connection to the shadow container."""
        return await asyncpg.connect(self.dsn, timeout=10.0)


def is_docker_available() -> bool:
    """Check if the Docker CLI is installed and running on the host system."""
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3.0,
        )
        return res.returncode == 0
    except Exception:
        return False


def _find_free_port(start_port: int = 15432, max_attempts: int = 100) -> int:
    """Find an available local TCP port for the shadow container."""
    import socket

    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise ShadowProvisioningError("No free local port found for shadow database")


async def wait_for_postgres_ready(
    dsn: str,
    timeout_seconds: float = 30.0,
    interval_seconds: float = 0.5,
) -> bool:
    """Poll the shadow database until it accepts connections or times out."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            conn = await asyncpg.connect(dsn, timeout=2.0)
            await conn.fetchval("SELECT 1")
            await conn.close()
            return True
        except Exception:
            await asyncio.sleep(interval_seconds)
    return False


async def provision_shadow_db(
    config: ShadowConfig | None = None,
) -> ShadowDatabase:
    """Provision a new ephemeral Docker container for shadow database replay."""
    cfg = config or ShadowConfig()
    if not is_docker_available():
        raise ShadowProvisioningError(
            "Docker is not available or running. Cannot provision shadow database container."
        )

    unique_id = uuid.uuid4().hex[:8]
    container_name = f"{cfg.container_prefix}-{unique_id}"
    port = cfg.port or _find_free_port()
    dsn = f"postgresql://{cfg.postgres_user}:{cfg.postgres_password}@127.0.0.1:{port}/{cfg.postgres_db}"

    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "-p", f"{port}:5432",
        "-e", f"POSTGRES_USER={cfg.postgres_user}",
        "-e", f"POSTGRES_PASSWORD={cfg.postgres_password}",
        "-e", f"POSTGRES_DB={cfg.postgres_db}",
        "-m", cfg.memory_limit,
        cfg.image,
    ]

    logger.info(f"Provisioning shadow container: {container_name} on port {port}")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            raise ShadowProvisioningError(f"docker run failed: {err_msg}")

        container_id = stdout.decode().strip()
        ready = await wait_for_postgres_ready(dsn, timeout_seconds=cfg.startup_timeout_seconds)
        if not ready:
            await teardown_shadow_db(container_name)
            raise ShadowProvisioningError(
                f"Shadow database failed to become ready within {cfg.startup_timeout_seconds}s"
            )

        return ShadowDatabase(
            container_id=container_id,
            container_name=container_name,
            port=port,
            dsn=dsn,
            is_ready=True,
        )
    except Exception as exc:
        logger.error(f"Error provisioning shadow database: {exc}")
        if not isinstance(exc, ShadowProvisioningError):
            raise ShadowProvisioningError(f"Failed to provision shadow database: {exc}") from exc
        raise


async def teardown_shadow_db(container_id_or_name: str) -> bool:
    """Stop and remove an ephemeral shadow database container."""
    if not is_docker_available():
        return False
    logger.info(f"Tearing down shadow container: {container_id_or_name}")
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", container_id_or_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        return proc.returncode == 0
    except Exception as exc:
        logger.warning(f"Failed to remove container {container_id_or_name}: {exc}")
        return False


async def install_candidate_optimization(
    connection: asyncpg.Connection,
    candidate_sql: str,
) -> dict[str, Any]:
    """Execute a candidate optimization (DDL/config) against the shadow database.

    Measures execution time and returns execution metadata.
    """
    start_time = time.monotonic()
    try:
        await connection.execute(candidate_sql)
        duration_ms = (time.monotonic() - start_time) * 1000.0
        return {
            "candidate_sql": candidate_sql,
            "success": True,
            "duration_ms": duration_ms,
            "error": None,
        }
    except Exception as exc:
        duration_ms = (time.monotonic() - start_time) * 1000.0
        logger.error(f"Failed to install candidate on shadow database: {exc}")
        return {
            "candidate_sql": candidate_sql,
            "success": False,
            "duration_ms": duration_ms,
            "error": str(exc),
        }


async def clone_schema_and_tables(
    source_conn: asyncpg.Connection,
    target_conn: asyncpg.Connection,
    table_names: Sequence[str],
    *,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    """Lightweight in-Python table cloner for test fixtures or sampled shadow runs."""
    cloned_tables = []
    for table in table_names:
        # Get column definitions
        cols = await source_conn.fetch(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
            """,
            table,
        )
        if not cols:
            continue

        col_defs = ", ".join(f'"{c["column_name"]}" {c["data_type"]}' for c in cols)
        await target_conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs})')

        # Copy data
        limit_clause = f" LIMIT {sample_limit}" if sample_limit else ""
        rows = await source_conn.fetch(f'SELECT * FROM "{table}"{limit_clause}')
        if rows:
            col_names = [f'"{c["column_name"]}"' for c in cols]
            placeholders = ", ".join(f"${i+1}" for i in range(len(col_names)))
            insert_sql = f'INSERT INTO "{table}" ({", ".join(col_names)}) VALUES ({placeholders})'
            for row in rows:
                await target_conn.execute(insert_sql, *row.values())

        cloned_tables.append(table)

    return {"status": "CLONED", "tables": cloned_tables, "sample_limit": sample_limit}


@asynccontextmanager
async def shadow_environment(
    config: ShadowConfig | None = None,
) -> AsyncGenerator[ShadowDatabase, None]:
    """Async context manager for automatic provisioning and teardown of shadow DB."""
    instance = await provision_shadow_db(config)
    try:
        yield instance
    finally:
        await teardown_shadow_db(instance.container_id)
