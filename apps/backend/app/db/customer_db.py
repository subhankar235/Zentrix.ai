"""
Customer Database Connection Manager.
Maintains isolated, per-connection asyncpg pools to monitored customer PostgreSQL databases.
Reference: ARCHITECTURE.md §4 (db/customer_db.py), §7, §14 & PRD.md §14
"""

import asyncio
import re
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Optional
import asyncpg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.core.security import decrypt_connection_string, encrypt_connection_string
from app.models.connection import DatabaseConnection

logger = get_logger(__name__)


def _prepare_asyncpg_dsn(raw_url: str) -> str:
    """
    Format and clean a decrypted PostgreSQL connection string for asyncpg.
    Strips driver prefixes and unneeded parameters while preserving SSL settings.
    """
    url = raw_url.strip()
    # Strip sqlalchemy driver schemes
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    elif url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # asyncpg accepts PostgreSQL's sslmode DSN option, but not channel_binding.
    if "channel_binding=" in url:
        url = re.sub(r"[?&]channel_binding=[^&]+", "", url)
        if "?" not in url and "&" in url:
            url = url.replace("&", "?", 1)

    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if "ssl" in query and "sslmode" not in query:
        query["sslmode"] = query.pop("ssl")
        url = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(query, doseq=True),
                parsed.fragment,
            )
        )

    return url


class CustomerConnectionManager:
    """
    Singleton connection manager caching asyncpg pools per monitored customer database.
    Decrypts connection strings just-in-time and ensures secrets are never logged.
    """

    def __init__(self) -> None:
        self._pools: Dict[uuid.UUID, asyncpg.Pool] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def get_customer_pool(
        self,
        connection_id: uuid.UUID,
        db: AsyncSession,
        min_size: int = 1,
        max_size: int = 10,
    ) -> asyncpg.Pool:
        """
        Retrieve or initialize an asyncpg.Pool for the given customer connection ID.
        """
        # Return cached active pool if present
        if connection_id in self._pools:
            pool = self._pools[connection_id]
            if not pool._closed:
                return pool

        async with self._lock:
            # Double-check inside lock
            if connection_id in self._pools and not self._pools[connection_id]._closed:
                return self._pools[connection_id]

            # Fetch connection metadata from application database
            stmt = select(DatabaseConnection).where(DatabaseConnection.id == connection_id)
            res = await db.execute(stmt)
            conn_record = res.scalar_one_or_none()

            if not conn_record:
                raise ValueError(f"Customer database connection {connection_id} not found")

            # Decrypt stored credentials just-in-time
            decrypted_conn_str = decrypt_connection_string(conn_record.encrypted_connection_string)
            dsn = _prepare_asyncpg_dsn(decrypted_conn_str)
            parsed_dsn = urlsplit(dsn)
            query = parse_qs(parsed_dsn.query, keep_blank_values=True)
            if "ssl" in query and "sslmode" not in query:
                query["sslmode"] = query.pop("ssl")
            if "sslmode" not in query and conn_record.ssl_mode:
                query["sslmode"] = [conn_record.ssl_mode]
                dsn = urlunsplit(
                    (
                        parsed_dsn.scheme,
                        parsed_dsn.netloc,
                        parsed_dsn.path,
                        urlencode(query, doseq=True),
                        parsed_dsn.fragment,
                    )
                )

            logger.info(
                f"Initializing customer database connection pool for connection {connection_id}",
                extra={"connection_id": str(connection_id)},
            )

            async def create_pool(pool_dsn: str) -> asyncpg.Pool:
                return await asyncpg.create_pool(
                    dsn=pool_dsn,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=30.0,
                    max_inactive_connection_lifetime=300.0,
                )

            try:
                pool = await create_pool(dsn)
                self._pools[connection_id] = pool
                return pool
            except Exception as e:
                setup_dsn = conn_record.encrypted_setup_connection_string
                if setup_dsn:
                    try:
                        # Repair a rotated or stale monitoring role using only
                        # the separately encrypted setup credential.
                        from app.services.connection_service import _provision_monitoring_dsn

                        repaired_raw, monitoring_username = await _provision_monitoring_dsn(
                            decrypt_connection_string(setup_dsn)
                        )
                        conn_record.encrypted_connection_string = encrypt_connection_string(repaired_raw)
                        conn_record.username = monitoring_username
                        await db.commit()
                        repaired_dsn = _prepare_asyncpg_dsn(repaired_raw)
                        pool = await create_pool(repaired_dsn)
                        self._pools[connection_id] = pool
                        return pool
                    except Exception as repair_error:
                        logger.error(
                            "Failed to repair customer database credentials",
                            extra={"connection_id": str(connection_id), "error": str(repair_error)},
                        )
                logger.error(
                    f"Failed to create asyncpg pool for connection {connection_id}: {e}",
                    extra={"connection_id": str(connection_id)},
                )
                raise

    @asynccontextmanager
    async def acquire_connection(
        self,
        connection_id: uuid.UUID,
        db: AsyncSession,
    ) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Async context manager yielding a dedicated connection from the customer pool.
        """
        pool = await self.get_customer_pool(connection_id, db=db)
        async with pool.acquire() as connection:
            yield connection

    async def close_customer_pool(self, connection_id: uuid.UUID) -> None:
        """
        Close and remove a specific customer connection pool.
        """
        async with self._lock:
            pool = self._pools.pop(connection_id, None)
            if pool and not pool._closed:
                await pool.close()
                logger.info(f"Closed connection pool for {connection_id}")

    async def close_all_pools(self) -> None:
        """
        Close all active customer connection pools (called during application shutdown).
        """
        async with self._lock:
            for conn_id, pool in list(self._pools.items()):
                if not pool._closed:
                    try:
                        await pool.close()
                    except Exception as e:
                        logger.warning(f"Error closing customer pool {conn_id}: {e}")
            self._pools.clear()
            logger.info("All customer database connection pools closed successfully")


# Global singleton instance
customer_connection_manager = CustomerConnectionManager()


async def get_customer_pool(connection_id: uuid.UUID, db: AsyncSession) -> asyncpg.Pool:
    """Convenience accessor for customer connection manager pool."""
    return await customer_connection_manager.get_customer_pool(connection_id, db=db)
