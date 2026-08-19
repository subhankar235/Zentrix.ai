"""
Security, Cryptography, and Authentication Primitives.
Reference: ARCHITECTURE.md §4 (core/security.py), §10, §14 & PRD.md §14
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import get_settings


# ─── Password Hashing & Verification ─────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt with a securely generated salt.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ─── JWT Authentication Token Handling ───────────────────────────────────────

def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT access token.
    Used for user session authentication in API headers and secure httpOnly cookies.
    """
    settings = get_settings()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises ValueError on token expiration or invalid signature.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Authentication token has expired")
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid authentication token: {e}")


# ─── Connection Credential Encryption (Fernet / AES) ─────────────────────────

def _get_fernet_instance(key: Optional[str] = None) -> Fernet:
    """
    Get a Fernet cipher instance using the configured CONNECTION_ENCRYPTION_KEY.
    """
    encryption_key = key or get_settings().CONNECTION_ENCRYPTION_KEY
    if isinstance(encryption_key, str):
        encryption_key_bytes = encryption_key.encode("utf-8")
    else:
        encryption_key_bytes = encryption_key
    return Fernet(encryption_key_bytes)


def encrypt_connection_string(conn_str: str, key: Optional[str] = None) -> str:
    """
    Encrypt a customer PostgreSQL connection string for secure storage at rest.
    """
    fernet = _get_fernet_instance(key)
    encrypted_bytes = fernet.encrypt(conn_str.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_connection_string(encrypted_conn_str: str, key: Optional[str] = None) -> str:
    """
    Decrypt an encrypted customer connection string in-memory just-in-time for use.
    Never logs decrypted credentials.
    """
    fernet = _get_fernet_instance(key)
    try:
        decrypted_bytes = fernet.decrypt(encrypted_conn_str.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        raise ValueError("Failed to decrypt database connection string: invalid encryption key or corrupted data")
