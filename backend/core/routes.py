"""Core HTTP routes — auth (login / refresh / me) + admin user/group endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser, requires
from backend.core.audit import set_audit_context, _request_id_ctx
from backend.core.db import SessionDep
from backend.core.models import Company, Group, Permission, User
from backend.core.schemas import (
    CompanyCreate,
    CompanyRead,
    GroupCreate,
    GroupRead,
    LoginRequest,
    PermissionRead,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserRead,
)
from backend.core.security import (
    create_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/api/v1")
auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])
groups_router = APIRouter(prefix="/groups", tags=["groups"])
companies_router = APIRouter(prefix="/companies", tags=["companies"])


# ── Auth ───────────────────────────────────────────────────────────────


@auth_router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, session: SessionDep) -> TokenPair:
    stmt = (
        select(User)
        .where(User.email == body.email, User.deleted_at.is_(None))
        .options(
            selectinload(User.groups),
            selectinload(User.companies),
            selectinload(User.default_company),
        )
    )
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    user.last_login_at = datetime.now(UTC)
    set_audit_context(_request_id_ctx.get(), user.id)

    return TokenPair(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@auth_router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, session: SessionDep) -> TokenPair:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token") from exc

    user = (
        await session.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")

    return TokenPair(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@auth_router.get("/me", response_model=UserRead)
async def me(user: CurrentUser, session: SessionDep) -> User:
    # Refresh with companies relationship loaded.
    stmt = (
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.groups),
            selectinload(User.companies),
            selectinload(User.default_company),
        )
    )
    return (await session.execute(stmt)).scalar_one()


# ── Companies ──────────────────────────────────────────────────────────


@companies_router.get("", response_model=list[CompanyRead])
async def list_companies(
    session: SessionDep, user: CurrentUser
) -> list[Company]:
    """Return only the companies the current user is allowed to see.

    Superusers see every active company; everyone else sees their
    user_company memberships.
    """
    if user.is_superuser:
        stmt = (
            select(Company)
            .where(Company.deleted_at.is_(None))
            .order_by(Company.code)
        )
        return list((await session.execute(stmt)).scalars().all())
    return list(user.companies)


@companies_router.post(
    "",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_company(
    body: CompanyCreate, session: SessionDep, user: CurrentUser
) -> Company:
    if not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only superusers can create companies")
    company = Company(**body.model_dump(), is_active=True)
    session.add(company)
    await session.flush()
    return company


@companies_router.post("/{company_id}/switch", response_model=UserRead)
async def switch_company(
    company_id: int, session: SessionDep, user: CurrentUser
) -> User:
    """Set the current user's default company for subsequent sessions.

    Returns the refreshed user record with companies + default loaded.
    """
    company = await session.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "company not found")
    if not user.is_superuser and company not in user.companies:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this company")
    user.default_company_id = company_id

    stmt = (
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.groups),
            selectinload(User.companies),
            selectinload(User.default_company),
        )
    )
    return (await session.execute(stmt)).scalar_one()


# ── Users (admin) ──────────────────────────────────────────────────────


@users_router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requires("core.user:create"))],
)
async def create_user(body: UserCreate, session: SessionDep) -> User:
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        is_active=True,
        is_superuser=body.is_superuser,
    )
    session.add(user)
    await session.flush()
    return user


@users_router.get("", response_model=list[UserRead])
async def list_users(
    session: SessionDep,
    _user: CurrentUser,
    limit: int = 100,
    offset: int = 0,
) -> list[User]:
    stmt = (
        select(User)
        .where(User.deleted_at.is_(None))
        .order_by(User.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


# ── Groups + Permissions ───────────────────────────────────────────────


@groups_router.get("/permissions", response_model=list[PermissionRead])
async def list_permissions(session: SessionDep, _user: CurrentUser) -> list[Permission]:
    return list(
        (await session.execute(select(Permission).order_by(Permission.model, Permission.action)))
        .scalars()
        .all()
    )


@groups_router.post(
    "",
    response_model=GroupRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_group(body: GroupCreate, session: SessionDep, _user: CurrentUser) -> Group:
    group = Group(name=body.name, description=body.description)
    if body.permission_codes:
        perms = await _resolve_permissions(session, body.permission_codes)
        group.permissions = perms
    session.add(group)
    await session.flush()
    return group


@groups_router.get("", response_model=list[GroupRead])
async def list_groups(session: SessionDep, _user: CurrentUser) -> list[Group]:
    return list(
        (
            await session.execute(
                select(Group)
                .where(Group.deleted_at.is_(None))
                .options(selectinload(Group.permissions))
                .order_by(Group.name)
            )
        )
        .scalars()
        .all()
    )


async def _resolve_permissions(session, codes: list[str]) -> list[Permission]:
    pairs = [tuple(c.split(":", 1)) for c in codes if ":" in c]
    if not pairs:
        return []

    from sqlalchemy import or_, and_

    stmt = select(Permission).where(
        or_(*(and_(Permission.model == m, Permission.action == a) for m, a in pairs))
    )
    perms = list((await session.execute(stmt)).scalars().all())
    found_codes = {p.code for p in perms}
    missing = [c for c in codes if c not in found_codes]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unknown permission codes: {', '.join(missing)}",
        )
    return perms


router.include_router(auth_router)
router.include_router(users_router)
router.include_router(groups_router)
router.include_router(companies_router)
