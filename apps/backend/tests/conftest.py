import pytest
from app.db.session import async_session_factory


@pytest.fixture
def db_session_factory():
    """Yield standard async session factory."""
    return async_session_factory

