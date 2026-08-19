"""
Application Database async connection session layer.
Reference: ARCHITECTURE.md §4 (db/session.py) & §7
"""

from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import Base

logger = get_logger(__name__)
settings = get_settings()

# Configure the async SQLAlchemy engine for PostgreSQL / Neon
engine: AsyncEngine = create_async_engine(
    settings.APP_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Async session factory
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async database session with automatic
    rollback on error and guaranteed closure.

    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(f"Database session rolled back due to error: {exc}", exc_info=True)
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    """
    Execute a lightweight SELECT 1 query to verify application DB connectivity.
    """
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False
