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
import re
import shutil
import subprocess
import tempfile
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

_ALLOWED_SHADOW_SQL = (
    re.compile(
        r"^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?"
        r"(?:IF\s+NOT\s+EXISTS\s+)?[A-Za-z_][A-Za-z0-9_$]*\s+ON\s+"
        r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?\s*\("
        r"[A-Za-z_][A-Za-z0-9_$]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_$]*)*\)\s*;?\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*ANALYZE(?:\s+[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?)?\s*;?\s*$", re.IGNORECASE),
    re.compile(r"^\s*VACUUM\s+ANALYZE\s+[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?\s*;?\s*$", re.IGNORECASE),
)


async def _run_command(
    args: list[str],
    *,
    input_bytes: bytes | None = None,
    timeout_seconds: float = 120.0,
) -> subprocess.CompletedProcess[bytes]:
    """Run external tools without relying on Windows asyncio subprocess support."""
    return await asyncio.to_thread(
        subprocess.run,
        args,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )


class ShadowProvisioningError(RuntimeError):
    """Raised when an ephemeral shadow container cannot be provisioned."""


@dataclass
class ShadowConfig:
    image: str = field(default_factory=lambda: get_settings().SHADOW_DB_IMAGE)
    container_prefix: str = "zentrix-shadow"
    postgres_user: str = "postgres"
    postgres_password: str = "shadowpass"
    postgres_db: str = "shadow_test"
    host: str = field(default_factory=lambda: get_settings().SHADOW_DB_HOST)
    port: int | None = None
    memory_limit: str = "2g"
    startup_timeout_seconds: float = 30.0
    mode: str = field(default_factory=lambda: get_settings().SHADOW_CLONE_MODE)
    sample_limit: int = field(default_factory=lambda: get_settings().SHADOW_SAMPLE_LIMIT)


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
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        res = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10.0,
        )
        return res.returncode == 0
    except Exception:
        return False


def _docker_client_dsn(dsn: str) -> str:
    """Make a host-published shadow DSN reachable from a Docker client."""
    return dsn.replace("@127.0.0.1:", "@host.docker.internal:").replace(
        "@localhost:", "@host.docker.internal:"
    )


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
    dsn = f"postgresql://{cfg.postgres_user}:{cfg.postgres_password}@{cfg.host}:{port}/{cfg.postgres_db}"

    cmd = [
        shutil.which("docker") or "docker", "run", "-d",
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
        # The first run may need to pull the PostgreSQL image, especially on a fresh Docker host.
        result = await _run_command(
            cmd,
            timeout_seconds=max(120.0, cfg.startup_timeout_seconds + 90.0),
        )
        if result.returncode != 0:
            err_msg = result.stderr.decode(errors="replace").strip() or "no error details returned by Docker"
            raise ShadowProvisioningError(f"docker run failed: {err_msg}")

        container_id = result.stdout.decode(errors="replace").strip()
        ready = await wait_for_postgres_ready(dsn, timeout_seconds=cfg.startup_timeout_seconds)
        if not ready:
            await teardown_shadow_db(container_name)
            raise ShadowProvisioningError(
                f"Shadow database failed to become ready within {cfg.startup_timeout_seconds}s "
                f"(container={container_name}, port={port}); inspect with 'docker logs {container_name}'"
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
            raise ShadowProvisioningError(
                f"Failed to provision shadow database ({type(exc).__name__}): {exc!r}"
            ) from exc
        raise


async def teardown_shadow_db(container_id_or_name: str) -> bool:
    """Stop and remove an ephemeral shadow database container."""
    if not is_docker_available():
        return False
    logger.info(f"Tearing down shadow container: {container_id_or_name}")
    try:
        result = await _run_command(
            [shutil.which("docker") or "docker", "rm", "-f", container_id_or_name],
            timeout_seconds=30.0,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.warning(f"Failed to remove shadow container: {exc}")
        return False


async def _dump_and_restore(
    source_dsn: str,
    target_dsn: str,
    *,
    schema_only: bool = False,
    image: str = "pgvector/pgvector:pg18",
) -> None:
    """Clone through a temporary custom-format archive with safe cleanup."""
    archive_path = tempfile.mktemp(prefix="zentrix-shadow-", suffix=".dump")
    try:
        local_clients = shutil.which("pg_dump") and shutil.which("pg_restore")
        dump_source = source_dsn if local_clients else _docker_client_dsn(source_dsn)
        # Agent execution history is application audit data, not customer
        # workload data, and may be protected by row-level policies. It is not
        # required for replaying customer queries in the shadow database.
        dump_args = [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            # HypoPG is evaluated against the customer connection before the
            # shadow run. The pgvector image does not necessarily ship with
            # the extension, so do not restore its CREATE EXTENSION command.
            "--exclude-extension=hypopg",
            "--exclude-table-data=public.agent_logs",
            "--exclude-table-data=public.conversation_context",
            "--exclude-table-data=public.drafts",
            "--dbname",
            dump_source,
        ]
        if schema_only:
            dump_args.insert(2, "--schema-only")
        if local_clients:
            dump_args.extend(["--file", archive_path])
        else:
            dump_args = [shutil.which("docker") or "docker", "run", "--rm", "-i", image, *dump_args]
        dump = await _run_command(dump_args)
        dump_stderr = dump.stderr
        if not local_clients:
            dump_stdout = dump.stdout
            with open(archive_path, "wb") as archive:
                archive.write(dump_stdout)
        if dump.returncode != 0:
            raise ShadowProvisioningError(
                f"Shadow dump failed ({'local pg_dump' if local_clients else 'Docker PostgreSQL client'}): "
                f"{dump_stderr.decode(errors='replace').strip() or 'no error details returned'}"
            )

        restore_target = target_dsn if local_clients else _docker_client_dsn(target_dsn)
        restore_args = [
            "pg_restore", "--no-owner", "--no-acl", "--clean", "--if-exists",
            "--exit-on-error", "--dbname", restore_target,
        ]
        if local_clients:
            restore_args.append(archive_path)
            restore = await _run_command(restore_args)
        else:
            with open(archive_path, "rb") as archive:
                archive_bytes = archive.read()
            restore = await _run_command(
                [shutil.which("docker") or "docker", "run", "--rm", "-i", image, *restore_args],
                input_bytes=archive_bytes,
            )
        restore_stderr = restore.stderr
        if restore.returncode != 0:
            raise ShadowProvisioningError(
                f"Shadow restore failed ({'local pg_restore' if local_clients else 'Docker PostgreSQL client'}): "
                f"{restore_stderr.decode(errors='replace').strip() or 'no error details returned'}"
            )
    finally:
        try:
            os.unlink(archive_path)
        except FileNotFoundError:
            pass


async def clone_customer_database(
    source_dsn: str,
    target_dsn: str,
    *,
    mode: str = "full_clone",
    sample_limit: int = 10000,
) -> dict[str, Any]:
    """Clone a customer PostgreSQL database into the fresh shadow database.

    The client utilities are executed server-side and credentials are never
    logged. A failed dump or restore aborts the experiment instead of falling
    back to synthetic metrics.
    """
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"full_clone", "schema_only", "sampled"}:
        raise ShadowProvisioningError(
            f"Unsupported shadow clone mode {mode!r}; use full_clone, schema_only, or sampled"
        )
    if normalized_mode == "full_clone":
        await _dump_and_restore(source_dsn, target_dsn, image=get_settings().SHADOW_DB_IMAGE)
        return {"mode": normalized_mode, "sample_limit": None}
    if normalized_mode == "schema_only":
        await _dump_and_restore(source_dsn, target_dsn, schema_only=True, image=get_settings().SHADOW_DB_IMAGE)
        return {"mode": normalized_mode, "sample_limit": None}

    await _dump_and_restore(source_dsn, target_dsn, schema_only=True, image=get_settings().SHADOW_DB_IMAGE)
    source = await asyncpg.connect(source_dsn)
    target = await asyncpg.connect(target_dsn)
    try:
        tables = await source.fetch(
            """
            SELECT schemaname, tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename
            """
        )
        table_names = [
            f"{row['schemaname']}.{row['tablename']}" if row["schemaname"] != "public" else row["tablename"]
            for row in tables
        ]
        result = await clone_schema_and_tables(
            source, target, table_names, sample_limit=max(1, sample_limit)
        )
        return {"mode": normalized_mode, "sample_limit": sample_limit, **result}
    finally:
        await source.close()
        await target.close()


async def install_candidate_optimization(
    connection: asyncpg.Connection,
    candidate_sql: str,
) -> dict[str, Any]:
    """Execute a candidate optimization (DDL/config) against the shadow database.

    Measures execution time and returns execution metadata.
    """
    start_time = time.monotonic()
    cleaned = candidate_sql.strip()
    if not any(pattern.match(cleaned) for pattern in _ALLOWED_SHADOW_SQL):
        return {
            "candidate_sql": candidate_sql,
            "success": False,
            "duration_ms": 0.0,
            "error": "Candidate SQL is outside the supported index/statistics/vacuum action set",
        }
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
        parts = table.split(".", 1)
        schema_name, table_name = parts if len(parts) == 2 else ("public", parts[0])
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", schema_name) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_$]*", table_name
        ):
            continue
        # Get column definitions
        cols = await source_conn.fetch(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            schema_name,
            table_name,
        )
        if not cols:
            continue

        col_defs = ", ".join(f'"{c["column_name"]}" {c["data_type"]}' for c in cols)
        qualified = f'"{schema_name}"."{table_name}"'
        await target_conn.execute(f"CREATE TABLE IF NOT EXISTS {qualified} ({col_defs})")

        # Copy data
        limit_clause = f" LIMIT {sample_limit}" if sample_limit else ""
        rows = await source_conn.fetch(f"SELECT * FROM {qualified}{limit_clause}")
        if rows:
            col_names = [f'"{c["column_name"]}"' for c in cols]
            placeholders = ", ".join(f"${i+1}" for i in range(len(col_names)))
            insert_sql = f"INSERT INTO {qualified} ({', '.join(col_names)}) VALUES ({placeholders})"
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
