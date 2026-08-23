from app.db.customer_db import _prepare_asyncpg_dsn


def test_customer_dsn_preserves_asyncpg_sslmode():
    dsn = _prepare_asyncpg_dsn("postgresql://user:password@db.example.com/app?sslmode=require")

    assert "sslmode=require" in dsn
    assert "ssl=require" not in dsn


def test_customer_dsn_normalizes_ssl_alias_to_sslmode():
    dsn = _prepare_asyncpg_dsn("postgresql://user:password@db.example.com/app?ssl=require")

    assert "sslmode=require" in dsn
    assert "ssl=require" not in dsn
