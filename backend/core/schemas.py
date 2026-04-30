"""Pydantic schemas for the core module's API surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _ORMSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth ───────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Company ────────────────────────────────────────────────────────────


class CompanyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = None
    tax_id: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    currency: str = Field(default="THB", min_length=3, max_length=3)
    locale: str = "th-TH"
    timezone: str = "Asia/Bangkok"
    parent_id: int | None = None


class CompanyRead(_ORMSchema):
    id: int
    code: str
    name: str
    legal_name: str | None = None
    tax_id: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    currency: str
    locale: str
    timezone: str
    parent_id: int | None = None
    is_active: bool


# ── User ───────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=255)
    is_superuser: bool = False
    default_company_id: int | None = None
    company_ids: list[int] = Field(default_factory=list)


class UserRead(_ORMSchema):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime
    default_company_id: int | None = None
    preferred_locale: str
    companies: list[CompanyRead] = Field(default_factory=list)
    default_company: CompanyRead | None = None


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
