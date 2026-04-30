"""Pydantic schemas for the core module's API surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _ORMSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth ───────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ── User ───────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=255)
    is_superuser: bool = False


class UserRead(_ORMSchema):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime


# ── Group / Permission ─────────────────────────────────────────────────


class PermissionRead(_ORMSchema):
    id: int
    model: str
    action: str
    description: str | None = None


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    permission_codes: list[str] = Field(default_factory=list)


class GroupRead(_ORMSchema):
    id: int
    name: str
    description: str | None = None
    permissions: list[PermissionRead] = Field(default_factory=list)
