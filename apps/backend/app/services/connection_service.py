"""
Connection Onboarding & Permission Check Service.
Handles database registration, extension verification (pg_stat_statements, hypopg), and telemetry summary.
Reference: TECHSTACK.md User Connection Workflow, PRD.md §4 Core User Journey & ARCHITECTURE.md §4
"""

import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import asyncpg
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.core.security import decrypt_connection_string, encrypt_connection_string
from app.db.customer_db import _prepare_asyncpg_dsn, customer_connection_manager
from app.models.connection import DatabaseConnection
from app.models.telemetry import QueryMetric, TableMetric
from app.schemas.connection import ConnectionCreate, ConnectionTestResponse
from app.schemas.telemetry import (
    QueryMetricOut,
    TableMetricOut,
    TelemetrySummaryResponse,
)
from app.tools import pg_introspection

logger = get_logger(__name__)


async def verify_raw_dsn(raw_conn_str: str) -> ConnectionTestResponse:
    """
    Connect to a PostgreSQL target using asyncpg, test credentials, measure latency,
    and verify required extensions and view permissions.
    """

    dsn = _prepare_asyncpg_dsn(raw_conn_str)
    permissions: Dict[str, bool] = {
        "pg_stat_statements": False,
        "hypopg": False,
        "pg_stat_activity": False,
        "pg_stat_user_tables": False,
        "pg_statio_user_tables": False,
        "read_only_role": False,
    }
    postgres_version: Optional[str] = None
    start_time = time.perf_counter()

    try:
        conn = await asyncpg.connect(dsn, timeout=10.0)
    except Exception as e:
        logger.warning(f"Connection test failed: {e}")
        return ConnectionTestResponse(
            success=False,
            postgres_version=None,
            permissions=permissions,
            latency_ms=None,
            error=f"Connection failed: {str(e)}",
        )

    try:
        # 1. Measure latency with simple ping
        await conn.fetchval("SELECT 1;")
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 2. Get server version
        postgres_version = await conn.fetchval("SELECT version();")

        # 3. Check pg_stat_statements extension & query permission
        try:
            ext_exists = await conn.fetchval(
                "SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements';"
            )
            if ext_exists:
                # Test querying the view
                await conn.fetchval("SELECT count(*) FROM pg_stat_statements LIMIT 1;")
                permissions["pg_stat_statements"] = True
        except Exception:
            permissions["pg_stat_statements"] = False

        # 4. Check hypopg extension (optional / recommended)
        try:
            hypopg_exists = await conn.fetchval(
                "SELECT 1 FROM pg_extension WHERE extname = 'hypopg';"
            )
            if hypopg_exists:
                permissions["hypopg"] = True
        except Exception:
            permissions["hypopg"] = False

        # 5. Check pg_stat_activity access
        try:
            await conn.fetchval("SELECT count(*) FROM pg_stat_activity LIMIT 1;")
            permissions["pg_stat_activity"] = True
        except Exception:
            permissions["pg_stat_activity"] = False

        # 6. Check pg_stat_user_tables access
        try:
            await conn.fetchval("SELECT count(*) FROM pg_stat_user_tables LIMIT 1;")
            permissions["pg_stat_user_tables"] = True
        except Exception:
            permissions["pg_stat_user_tables"] = False

        # 7. Check pg_statio_user_tables access
        try:
            await conn.fetchval("SELECT count(*) FROM pg_statio_user_tables LIMIT 1;")
            permissions["pg_statio_user_tables"] = True
        except Exception:
            permissions["pg_statio_user_tables"] = False

        # 8. Check that the monitoring role is not an elevated write-capable role.
        # Keep this as an explicit warning for now so existing targets can still
        # be inspected while the user creates a dedicated monitoring role.
        try:
            read_only = await conn.fetchval(
                """
                SELECT NOT rolsuper
                   AND NOT rolcreaterole
                   AND NOT rolcreatedb
                   AND NOT has_schema_privilege(current_user, 'public', 'CREATE')
                FROM pg_roles
                WHERE rolname = current_user;
                """
            )
            permissions["read_only_role"] = bool(read_only)
        except Exception:
            permissions["read_only_role"] = False

        # Build response
        missing = []
        if not permissions["pg_stat_statements"]:
            missing.append("pg_stat_statements (required for query telemetry)")

        error_msg = None
        if missing:
            error_msg = f"Connected successfully, but required monitoring checks failed: {', '.join(missing)}"

        return ConnectionTestResponse(
            success=True,
            postgres_version=postgres_version,
            permissions=permissions,
            latency_ms=latency_ms,
            error=error_msg,
        )

    finally:
        await conn.close()


class ConnectionService:
    """
    Business logic layer for registering, testing, and managing monitored database connections.
    """

    @staticmethod
    def _build_connection_string(conn_in: ConnectionCreate) -> str:
        if conn_in.connection_string:
            return conn_in.connection_string.strip()
        return (
            f"postgresql://{conn_in.username}:{conn_in.password or ''}@"
            f"{conn_in.host}:{conn_in.port}/{conn_in.database_name}?sslmode={conn_in.ssl_mode}"
        )

    async def create_connection(
        self,
        user_id: uuid.UUID,
        conn_in: ConnectionCreate,
        db: AsyncSession,
    ) -> DatabaseConnection:
        """
        Encrypt credentials, perform initial reachability/permission check, and persist connection.
        """
        raw_conn_str = self._build_connection_string(conn_in)
        encrypted_str = encrypt_connection_string(raw_conn_str)

        # Run non-blocking test check to populate initial permission status
        test_result = await verify_raw_dsn(raw_conn_str)
        if not test_result.success:
            raise ValueError(test_result.error or "Database connection checks failed")

        existing_stmt = (
            select(DatabaseConnection)
            .where(
                DatabaseConnection.user_id == user_id,
                func.lower(DatabaseConnection.host) == conn_in.host.strip().lower(),
                DatabaseConnection.port == conn_in.port,
                func.lower(DatabaseConnection.database_name) == conn_in.database_name.strip().lower(),
                func.lower(DatabaseConnection.username) == conn_in.username.strip().lower(),
            )
            .order_by(DatabaseConnection.created_at.desc())
        )
        existing = (await db.execute(existing_stmt)).scalars().first()

        if existing:
            existing.name = conn_in.name
            existing.encrypted_connection_string = encrypted_str
            existing.provider = conn_in.provider
            existing.ssl_mode = conn_in.ssl_mode
            existing.permission_status = test_result.permissions
            existing.last_checked_at = datetime.now(timezone.utc)
            existing.is_active = True
            await db.commit()
            await db.refresh(existing)
            return existing

        connection = DatabaseConnection(
            user_id=user_id,
            name=conn_in.name,
            encrypted_connection_string=encrypted_str,
            host=conn_in.host,
            port=conn_in.port,
            database_name=conn_in.database_name,
            username=conn_in.username,
            ssl_mode=conn_in.ssl_mode,
            provider=conn_in.provider,
            permission_status=test_result.permissions,
            last_checked_at=datetime.now(timezone.utc),
            is_active=True,
        )
        db.add(connection)
        await db.commit()
        await db.refresh(connection)
        return connection

    async def test_connection(
        self,
        connection_id: uuid.UUID,
        user_id: uuid.UUID,
        is_superuser: bool,
        db: AsyncSession,
    ) -> ConnectionTestResponse:
        """
        Decrypt connection string just-in-time and test database reachability and permissions.
        Updates connection permission status in database.
        """
        stmt = select(DatabaseConnection).where(DatabaseConnection.id == connection_id)
        if not is_superuser:
            stmt = stmt.where(DatabaseConnection.user_id == user_id)

        res = await db.execute(stmt)
        conn_record = res.scalar_one_or_none()
        if not conn_record:
            return ConnectionTestResponse(
                success=False,
                error="Database connection not found or unauthorized",
            )

        decrypted_str = decrypt_connection_string(conn_record.encrypted_connection_string)
        test_result = await verify_raw_dsn(decrypted_str)


        # Update cached permission status in DB
        conn_record.permission_status = test_result.permissions
        conn_record.last_checked_at = datetime.now(timezone.utc)
        await db.commit()

        return test_result

    async def list_connections(
        self,
        user_id: uuid.UUID,
        is_superuser: bool,
        db: AsyncSession,
    ) -> List[DatabaseConnection]:
        """
        List active database connections.
        """
        stmt = select(DatabaseConnection).order_by(DatabaseConnection.created_at.desc())
        if not is_superuser:
            stmt = stmt.where(DatabaseConnection.user_id == user_id)

        res = await db.execute(stmt)
        connections = list(res.scalars().all())
        unique_connections: list[DatabaseConnection] = []
        seen_targets: set[tuple[str, int, str, str]] = set()
        for connection in connections:
            target = (
                connection.host.strip().lower(),
                connection.port,
                connection.database_name.strip().lower(),
                connection.username.strip().lower(),
            )
            if target in seen_targets:
                continue
            seen_targets.add(target)
            unique_connections.append(connection)
        return unique_connections

    async def get_connection(
        self,
        connection_id: Any,
        user_id: uuid.UUID,
        is_superuser: bool,
        db: AsyncSession,
    ) -> Optional[DatabaseConnection]:
        """
        Get connection by ID (UUID or slug/name).
        """
        if isinstance(connection_id, str):
            try:
                conn_uuid = uuid.UUID(connection_id)
                stmt = select(DatabaseConnection).where(DatabaseConnection.id == conn_uuid)
            except ValueError:
                stmt = select(DatabaseConnection).where(DatabaseConnection.name == connection_id)
        else:
            stmt = select(DatabaseConnection).where(DatabaseConnection.id == connection_id)

        if not is_superuser:
            stmt = stmt.where(DatabaseConnection.user_id == user_id)

        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def update_connection(
        self,
        connection_id: Any,
        user_id: uuid.UUID,
        is_superuser: bool,
        conn_in: Any,
        db: AsyncSession,
    ) -> Optional[DatabaseConnection]:
        """Update monitored database connection details."""
        conn_record = await self.get_connection(connection_id, user_id, is_superuser, db)
        if not conn_record:
            return None

        update_data = conn_in.model_dump(exclude_unset=True) if hasattr(conn_in, "model_dump") else dict(conn_in)
        for key, val in update_data.items():
            if hasattr(conn_record, key) and val is not None:
                setattr(conn_record, key, val)

        await db.commit()
        await db.refresh(conn_record)
        return conn_record

    async def delete_connection(
        self,
        connection_id: Any,
        user_id: uuid.UUID,
        is_superuser: bool,
        db: AsyncSession,
    ) -> bool:
        """
        Delete connection and close active connection pool.
        """
        conn_record = await self.get_connection(connection_id, user_id, is_superuser, db)
        if not conn_record:
            return False

        await customer_connection_manager.close_customer_pool(conn_record.id)
        await db.delete(conn_record)
        await db.commit()
        return True

    async def get_telemetry_summary(
        self,
        connection_id: Any,
        user_id: uuid.UUID,
        is_superuser: bool,
        db: AsyncSession,
    ) -> Optional[TelemetrySummaryResponse]:
        """
        Retrieve telemetry summary for a monitored database.
        Queries live database stats via customer_connection_manager or stored metrics.
        """
        conn_record = await self.get_connection(connection_id, user_id, is_superuser, db)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=24)

        if not conn_record:
            return None

        top_queries: List[QueryMetricOut] = []
        top_tables: List[TableMetricOut] = []
        cache_hit_ratio: Optional[float] = None
        query_telemetry_available = False
        table_telemetry_available = False

        # 1. Query live PostgreSQL stats if customer pool is reachable
        try:
            pool = await customer_connection_manager.get_customer_pool(conn_record.id, db)
            async with pool.acquire() as customer_conn:
                try:
                    live_queries = await pg_introspection.get_query_metrics(customer_conn, limit=15)
                    query_telemetry_available = True
                except Exception as exc:
                    logger.info(f"Query telemetry unavailable for connection {conn_record.id}: {exc}")
                    live_queries = []
                for q in live_queries:
                    calls = int(q.get("calls", 0) or 0)
                    mean_time = float(q.get("mean_exec_time", 0.0) or 0.0)
                    max_time = float(q.get("max_exec_time", 0.0) or 0.0)
                    total_time = float(q.get("total_exec_time", 0.0) or 0.0)
                    q_text = str(q.get("query") or "")
                    q_out = QueryMetricOut(
                        id=uuid.uuid4(),
                        connection_id=conn_record.id,
                        created_at=now,
                        timestamp=now,
                        db_id=q.get("db_id"),
                        userid=q.get("userid"),
                        queryid=q.get("queryid"),
                        query_hash=hashlib.sha256(q_text.encode("utf-8")).hexdigest()[:64],
                        query_text=q_text,
                        calls=calls,
                        mean_exec_time=round(mean_time, 2),
                        max_exec_time=round(max_time, 2),
                        min_exec_time=float(q.get("min_exec_time", 0.0) or 0.0),
                        total_exec_time=round(total_time, 2),
                        rows=int(q.get("rows", 0) or 0),
                        shared_blks_hit=int(q.get("shared_blks_hit", 0) or 0),
                        shared_blks_read=int(q.get("shared_blks_read", 0) or 0),
                        shared_blks_dirtied=int(q.get("shared_blks_dirtied", 0) or 0),
                        shared_blks_written=int(q.get("shared_blks_written", 0) or 0),
                        temp_blks_read=int(q.get("temp_blks_read", 0) or 0),
                        temp_blks_written=int(q.get("temp_blks_written", 0) or 0),
                        wal_bytes=int(q.get("wal_bytes", 0) or 0),
                        plans=int(q.get("plans", 0) or 0),
                        planning_time=float(q.get("planning_time", 0.0) or 0.0),
                    )
                    top_queries.append(q_out)

                try:
                    db_stats = await customer_conn.fetchrow(
                        "SELECT sum(blks_hit) as hit, sum(blks_read) as read FROM pg_stat_database;"
                    )
                    if db_stats and db_stats["hit"] is not None and db_stats["read"] is not None:
                        h = float(db_stats["hit"] or 0)
                        r = float(db_stats["read"] or 0)
                        if h + r > 0:
                            cache_hit_ratio = round(h / (h + r), 4)
                except Exception as exc:
                    logger.info(f"Cache telemetry unavailable for connection {conn_record.id}: {exc}")

                try:
                    live_tables = await pg_introspection.get_table_stats(customer_conn)
                    table_telemetry_available = True
                    for t in live_tables[:10]:
                        t_out = TableMetricOut(
                            id=uuid.uuid4(),
                            connection_id=conn_record.id,
                            created_at=now,
                            timestamp=now,
                            schema_name=t.get("schemaname", "public"),
                            table_name=t.get("relname", "table"),
                            live_tuples=int(t.get("n_live_tup", 0) or 0),
                            dead_tuples=int(t.get("n_dead_tup", 0) or 0),
                            dead_tuple_ratio=float(t.get("dead_tuple_ratio", 0.0) or 0.0),
                            table_size_bytes=int(t.get("table_size", 0) or 0),
                            index_size_bytes=int(t.get("index_size", 0) or 0),
                        )
                        top_tables.append(t_out)
                except Exception as exc:
                    logger.info(f"Table telemetry unavailable for connection {conn_record.id}: {exc}")
        except Exception as exc:
            logger.info(f"Using stored telemetry cache for connection {conn_record.id}: {exc}")

        # 2. Fallback to stored QueryMetric / TableMetric in app DB if pool had no results
        if not top_queries:
            q_stmt = (
                select(QueryMetric)
                .where(QueryMetric.connection_id == conn_record.id)
                .order_by(QueryMetric.total_exec_time.desc())
                .limit(10)
            )
            q_res = await db.execute(q_stmt)
            top_queries = [QueryMetricOut.model_validate(q) for q in q_res.scalars().all()]

        if not top_tables:
            t_stmt = (
                select(TableMetric)
                .where(TableMetric.connection_id == conn_record.id)
                .order_by(TableMetric.dead_tuple_ratio.desc())
                .limit(10)
            )
            t_res = await db.execute(t_stmt)
            top_tables = [TableMetricOut.model_validate(t) for t in t_res.scalars().all()]

        total_queries = sum(q.calls for q in top_queries) if top_queries else 0
        avg_latency = (
            sum(q.mean_exec_time for q in top_queries) / len(top_queries)
            if top_queries
            else 0.0
        )
        p95_latency = (
            max((q.max_exec_time for q in top_queries), default=0.0)
            if top_queries
            else 0.0
        )

        return TelemetrySummaryResponse(
            connection_id=conn_record.id,
            window_start=window_start,
            window_end=now,
            total_queries=total_queries,
            avg_latency_ms=round(avg_latency, 2),
            p95_latency_ms=round(p95_latency, 2),
            cache_hit_ratio=cache_hit_ratio,
            active_tables_count=len(top_tables),
            query_telemetry_available=query_telemetry_available,
            table_telemetry_available=table_telemetry_available,
            top_queries=top_queries,
            top_bloated_tables=top_tables,
        )


connection_service = ConnectionService()
