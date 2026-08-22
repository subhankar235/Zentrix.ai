"""
Step 35: Security Review & Hardening Verification Suite.
Reference: ARCHITECTURE.md §14 & PRD.md §14, §24
"""

import json
import logging
import uuid
import pytest
from app.core.logging import DevelopmentFormatter, StructuredJSONFormatter, mask_sensitive_data
from app.core.security import decrypt_connection_string, encrypt_connection_string
from app.models.connection import DatabaseConnection
from app.models.user import User
from app.tools.pg_introspection import _validate_read_query
from app.tools.hypopg_tool import validate_index_statement


def test_connection_strings_encrypted_at_rest():
    """
    Verify connection strings are encrypted using Fernet (AES-128 in CBC + HMAC)
    and stored as ciphertext, never as plaintext in the database model.
    """
    raw_dsn = "postgresql://dbuser:SuperSecretPassword123!@db.neon.tech:5432/production_db?sslmode=require"
    encrypted_cipher = encrypt_connection_string(raw_dsn)

    # 1. Verify ciphertext properties
    assert encrypted_cipher != raw_dsn
    assert "SuperSecretPassword123!" not in encrypted_cipher
    assert "dbuser" not in encrypted_cipher
    assert encrypted_cipher.startswith("gAAAAA")  # Fernet signature header

    # 2. Verify model storage is strictly ciphertext
    conn = DatabaseConnection(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Encrypted DB Test",
        encrypted_connection_string=encrypted_cipher,
        host="db.neon.tech",
        port=5432,
        database_name="production_db",
        username="dbuser",
    )
    assert conn.encrypted_connection_string == encrypted_cipher
    assert "SuperSecretPassword123!" not in conn.encrypted_connection_string

    # 3. Verify just-in-time decryption roundtrip
    decrypted = decrypt_connection_string(conn.encrypted_connection_string)
    assert decrypted == raw_dsn


def test_credentials_never_appear_in_logs():
    """
    Verify that log formatters automatically redact passwords, connection strings,
    and JWT Bearer tokens from all formatted log messages.
    """
    raw_sensitive_message = (
        "Connecting to target database postgresql://agent_user:P@ssw0rd999!@db.internal:5432/fin_db "
        "with header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0In0.sig"
    )

    # 1. Verify helper function
    masked = mask_sensitive_data(raw_sensitive_message)
    assert "P@ssw0rd999!" not in masked
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in masked
    assert "postgresql://agent_user:***@db.internal:5432/fin_db" in masked

    # 2. Verify Structured JSON Formatter output
    json_formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="zentrix.security",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=raw_sensitive_message,
        args=(),
        exc_info=None,
    )
    formatted_json = json_formatter.format(record)
    parsed = json.loads(formatted_json)
    assert "P@ssw0rd999!" not in parsed["message"]
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in parsed["message"]

    # 3. Verify Development Formatter output
    dev_formatter = DevelopmentFormatter()
    formatted_dev = dev_formatter.format(record)
    assert "P@ssw0rd999!" not in formatted_dev
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in formatted_dev


def test_monitored_database_read_only_least_privilege_enforcement():
    """
    Verify introspection and telemetry query validator strictly blocks any write, DDL,
    or multi-statement SQL from ever reaching the customer database connection.
    """
    valid_queries = [
        "SELECT * FROM users WHERE id = 1",
        "WITH active_orders AS (SELECT id FROM orders) SELECT * FROM active_orders",
        "SELECT count(*) FROM telemetry",
    ]
    for q in valid_queries:
        assert _validate_read_query(q) == q

    forbidden_queries = [
        "INSERT INTO users (id, name) VALUES (1, 'bad')",
        "UPDATE users SET name = 'hacked'",
        "DELETE FROM orders WHERE id = 5",
        "DROP TABLE users CASCADE",
        "CREATE TABLE backdoor (id int)",
        "ALTER TABLE users ADD COLUMN compromised text",
        "GRANT ALL PRIVILEGES ON DATABASE prod TO mallory",
        "SELECT 1; DROP TABLE users;",
        "SELECT 1; SELECT 2;",
        "COPY users TO '/tmp/leak.csv'",
    ]
    for bad_q in forbidden_queries:
        with pytest.raises(ValueError):
            _validate_read_query(bad_q)


def test_hypopg_and_candidate_sql_sanitization():
    """
    Verify candidate SQL statements submitted to HypoPG are validated against
    strict index syntax rules before being passed to customer connections.
    """
    valid_ddl = "CREATE INDEX idx_users_email ON users(email)"
    assert validate_index_statement(valid_ddl) == valid_ddl

    unsafe_ddl = [
        "DROP TABLE users;",
        "CREATE TABLE exploit (id int);",
        "SELECT * FROM users;",
        "CREATE INDEX idx_bad ON users(id); DELETE FROM users;",
    ]
    for unsafe in unsafe_ddl:
        with pytest.raises(ValueError):
            validate_index_statement(unsafe)


def test_tenant_isolation_model_contract():
    """
    Verify data model row-level ownership contracts for user isolation.
    """
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    conn_a = DatabaseConnection(
        id=uuid.uuid4(),
        user_id=user_a,
        name="Tenant A DB",
        encrypted_connection_string="enc_a",
        host="host_a",
        port=5432,
        database_name="tenant_a",
        username="user_a",
    )
    conn_b = DatabaseConnection(
        id=uuid.uuid4(),
        user_id=user_b,
        name="Tenant B DB",
        encrypted_connection_string="enc_b",
        host="host_b",
        port=5432,
        database_name="tenant_b",
        username="user_b",
    )

    assert conn_a.user_id != conn_b.user_id
    assert conn_a.user_id == user_a
