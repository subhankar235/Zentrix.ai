"""
User and Authentication Pydantic Schemas.
Reference: PRD.md §13, §24 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User login email address")
    full_name: Optional[str] = Field(None, description="User display name")
    role: str = Field(default="dba", description="User role ('admin', 'dba', 'viewer')")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Plaintext password for registration")


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="Login email")
    password: str = Field(..., description="Login password")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in_minutes: int = Field(..., description="Expiration window in minutes")
    user: UserOut = Field(..., description="Authenticated user profile")


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    iat: datetime
    role: Optional[str] = None
    email: Optional[str] = None
