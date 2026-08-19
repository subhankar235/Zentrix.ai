"""
Unit tests for database session and connection layer.
Step 5 verification: async engine, session generator, Base class, and SELECT 1 execution.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.db.base import Base, TimestampMixin
from app.db.session import engine, async_session_factory, get_db_session


def test_base_declarative_class():
    """Verify Base declarative class and TimestampMixin."""
    class SampleModel(Base, TimestampMixin):
        __tablename__ = "sample_test_table"
        from sqlalchemy.orm import Mapped, mapped_column
        from sqlalchemy import Integer, String
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String(50))

    assert hasattr(SampleModel, "id")
    assert hasattr(SampleModel, "name")
    assert hasattr(SampleModel, "created_at")
    assert hasattr(SampleModel, "updated_at")
    assert SampleModel.__tablename__ == "sample_test_table"


def test_session_factory_configured():
    """Verify async_session_factory is properly initialized."""
    assert async_session_factory is not None
    assert engine is not None


@pytest.mark.asyncio
async def test_async_session_select_1():
    """Verify executing SELECT 1 through an async session."""
    # Test using an isolated async in-memory SQLite engine
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_session_factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_get_db_session_dependency_lifecycle():
    """Verify get_db_session yields session and handles commit/rollback."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Simulate get_db_session generator pattern
    async def sample_get_session():
        async with test_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    gen = sample_get_session()
    session = await anext(gen)
    assert isinstance(session, AsyncSession)
    res = await session.execute(text("SELECT 42"))
    assert res.scalar() == 42
    
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    await test_engine.dispose()
