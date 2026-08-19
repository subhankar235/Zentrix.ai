"""
Integration tests for Step 11: Customer Database Connection Manager.
Tests just-in-time decryption, per-connection asyncpg pooling, query execution, caching, and cleanup.
"""

import uuid
import pytest
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings
from app.core.security import encrypt_connection_string
from app.db.customer_db import customer_connection_manager, _prepare_asyncpg_dsn
from app.models.connection import DatabaseConnection
from app.models.user import User



def test_prepare_asyncpg_dsn():
    """Verify DSN cleaner handles sqlalchemy scheme and SSL/channel_binding parameters."""
    url = "postgresql+asyncpg://user:pass@host.neon.tech:5432/neondb?sslmode=require&channel_binding=require"
    cleaned = _prepare_asyncpg_dsn(url)
    assert cleaned.startswith("postgresql://")
    assert "postgresql+asyncpg://" not in cleaned
    assert "channel_binding" not in cleaned
    assert "ssl=require" in cleaned


@pytest.mark.asyncio
async def test_customer_connection_manager_lifecycle():
    """
    Store an encrypted connection string, retrieve an asyncpg pool,
    execute query against target database, test caching and clean pool closing.
    """
    settings = get_settings()
    test_engine = create_async_engine(settings.APP_DATABASE_URL, poolclass=NullPool)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with test_session_factory() as session:
            # 1. Create a test user
            user = User(
                id=uuid.uuid4(),
                email=f"test_customer_{uuid.uuid4().hex[:8]}@zentrix.ai",
                hashed_password="hashed_pw_test",
                role="dba",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # 2. Store encrypted connection string using live application DB connection
            encrypted_dsn = encrypt_connection_string(settings.APP_DATABASE_URL)
            conn_id = uuid.uuid4()
            conn_record = DatabaseConnection(
                id=conn_id,
                user_id=user.id,
                name="Test Customer Neon DB",
                encrypted_connection_string=encrypted_dsn,
                host="ep-dawn-pond-axb4kmt3-pooler.c-4.us-east-2.aws.neon.tech",
                port=5432,
                database_name="neondb",
                username="neondb_owner",
                ssl_mode="require",
                provider="neon",
                is_active=True,
            )
            session.add(conn_record)
            await session.commit()

            try:
                # 3. Retrieve pool via manager
                pool = await customer_connection_manager.get_customer_pool(conn_id, db=session)
                assert pool is not None
                assert not pool._closed

                # 4. Acquire connection and execute query
                async with pool.acquire() as conn:
                    res = await conn.fetchval("SELECT 1")
                    assert res == 1

                    version = await conn.fetchval("SELECT version()")
                    assert "PostgreSQL" in version

                # 5. Verify caching returns identical pool instance
                pool2 = await customer_connection_manager.get_customer_pool(conn_id, db=session)
                assert pool is pool2

                # 6. Verify acquire_connection context manager
                async with customer_connection_manager.acquire_connection(conn_id, db=session) as conn:
                    val = await conn.fetchval("SELECT 42")
                    assert val == 42

                # 7. Close specific pool
                await customer_connection_manager.close_customer_pool(conn_id)
                assert conn_id not in customer_connection_manager._pools

            finally:
                # Cleanup test records
                await session.delete(conn_record)
                await session.delete(user)
                await session.commit()
                await customer_connection_manager.close_all_pools()
    finally:
        await test_engine.dispose()


