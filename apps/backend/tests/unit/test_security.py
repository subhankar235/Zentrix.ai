"""
Unit tests for security, cryptography, and authentication primitives.
Step 8 verification: password hashing, JWT encode/decode, and Fernet encryption round-trips.
"""

import uuid
from datetime import timedelta
import pytest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    encrypt_connection_string,
    decrypt_connection_string,
)


def test_password_hashing_and_verification_roundtrip():
    """Verify password hashing produces valid bcrypt hash and verifies correctly."""
    raw_password = "SuperSecretPassword123!@#"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_password_salting_uniqueness():
    """Verify separate hashes of identical passwords produce different salt/hash strings."""
    raw_password = "ConsistentPassword123!"
    hash1 = hash_password(raw_password)
    hash2 = hash_password(raw_password)

    assert hash1 != hash2
    assert verify_password(raw_password, hash1) is True
    assert verify_password(raw_password, hash2) is True


def test_jwt_create_and_decode_roundtrip():
    """Verify JWT creation with subject and extra claims decodes cleanly."""
    user_id = str(uuid.uuid4())
    token = create_access_token(
        subject=user_id,
        extra_claims={"role": "dba", "email": "dba@zentrix.ai"},
    )
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "dba"
    assert payload["email"] == "dba@zentrix.ai"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_expired_token_raises_error():
    """Verify expired JWT tokens raise ValueError."""
    user_id = "test-user-id"
    # Token expired 10 minutes ago
    expired_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(minutes=-10),
    )

    with pytest.raises(ValueError, match="expired"):
        decode_access_token(expired_token)


def test_jwt_tampered_token_raises_error():
    """Verify tampered JWT tokens raise ValueError."""
    token = create_access_token(subject="valid-user")
    tampered = token[:-5] + "XXXXX"

    with pytest.raises(ValueError, match="Invalid authentication token"):
        decode_access_token(tampered)


def test_fernet_connection_string_encryption_roundtrip():
    """Verify customer connection string encryption and decryption."""
    raw_connection_url = (
        "postgresql://customer_admin:SuperSecretPass@db.us-east-2.rds.amazonaws.com:5432/prod_db?sslmode=require"
    )
    encrypted = encrypt_connection_string(raw_connection_url)

    assert encrypted != raw_connection_url
    assert isinstance(encrypted, str)

    decrypted = decrypt_connection_string(encrypted)
    assert decrypted == raw_connection_url


def test_fernet_tampered_encrypted_data_raises_error():
    """Verify corrupted encrypted connection strings fail decryption gracefully."""
    raw_conn = "postgresql://user:pass@localhost:5432/test"
    encrypted = encrypt_connection_string(raw_conn)
    tampered = encrypted[:10] + "corrupted_payload" + encrypted[30:]

    with pytest.raises(ValueError, match="Failed to decrypt database connection string"):
        decrypt_connection_string(tampered)
