"""
FastAPI Request Dependencies (Authentication, DB Sessions, Connection Stubs).
Reference: ARCHITECTURE.md §4 (api/deps.py) & BACKEND_STEPS.md Step 8
"""

import uuid
from typing import Any, AsyncGenerator, Optional
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.user import User

logger = get_logger(__name__)
settings = get_settings()

COOKIE_AUTH_NAME = "access_token"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


def _extract_token_from_request(
    request: Request,
    header_token: Optional[str] = None,
    cookie_token: Optional[str] = None,
) -> Optional[str]:
    """
    Extract JWT authentication token from httpOnly secure cookie or Authorization Bearer header.
    """
    # 1. Check httpOnly Cookie first (per ARCHITECTURE.md §4)
    if cookie_token:
        return cookie_token

    cookie_val = request.cookies.get(COOKIE_AUTH_NAME)
    if cookie_val:
        return cookie_val

    # 2. Check Authorization Bearer header
    if header_token:
        return header_token

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    header_token: Optional[str] = Depends(oauth2_scheme),
    cookie_token: Optional[str] = Cookie(default=None, alias=COOKIE_AUTH_NAME),
) -> User:
    """
    FastAPI dependency resolving the authenticated User entity from JWT token.
    Validates token from httpOnly cookie or Bearer authorization header.
    """
    token = _extract_token_from_request(request, header_token=header_token, cookie_token=cookie_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Resolve user by UUID or email
    try:
        user_uuid = uuid.UUID(user_id_str)
        stmt = select(User).where(User.id == user_uuid)
    except ValueError:
        stmt = select(User).where(User.email == user_id_str)

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require the authenticated user to be an active superuser / administrator.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


async def get_customer_connection(
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    FastAPI dependency providing the active asyncpg connection pool
    for the requested customer database connection.
    Validates ownership and decrypts connection credentials just-in-time.
    """
    from app.models.connection import DatabaseConnection
    from app.db.customer_db import customer_connection_manager

    stmt = select(DatabaseConnection).where(DatabaseConnection.id == connection_id)
    if not current_user.is_superuser:
        stmt = stmt.where(DatabaseConnection.user_id == current_user.id)

    res = await db.execute(stmt)
    conn_record = res.scalar_one_or_none()
    if not conn_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found or unauthorized",
        )

    if not conn_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database connection is inactive",
        )

    try:
        pool = await customer_connection_manager.get_customer_pool(connection_id, db=db)
        return pool
    except Exception as e:
        logger.error(
            f"Failed to acquire pool for connection {connection_id}: {e}",
            extra={"connection_id": str(connection_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not establish connection to target database",
        )

