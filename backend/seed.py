"""Idempotent seed — bootstraps the initial superuser, base groups, and the
core permission catalogue.  Safe to re-run.

Usage::

    uv run python -m backend.seed
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.db import session_factory
from backend.core.models import Group, Permission, User
from backend.core.security import hash_password


class _Perm(NamedTuple):
    model: str
    action: str
    description: str


CORE_PERMISSIONS: list[_Perm] = [
    _Perm("core.user", "read", "List and view users"),
    _Perm("core.user", "create", "Create new users"),
    _Perm("core.user", "write", "Edit users"),
    _Perm("core.user", "delete", "Delete users"),
    _Perm("core.group", "read", "List and view groups"),
    _Perm("core.group", "write", "Create and edit groups"),
    _Perm("core.audit", "read", "Read the audit log"),
]


async def _ensure_permissions(session) -> dict[str, Permission]:
    existing = (await session.execute(select(Permission))).scalars().all()
    by_code = {p.code: p for p in existing}

    for perm in CORE_PERMISSIONS:
        code = f"{perm.model}:{perm.action}"
        if code not in by_code:
            row = Permission(model=perm.model, action=perm.action, description=perm.description)
            session.add(row)
            by_code[code] = row

    await session.flush()
    return by_code


async def _ensure_admin_group(session, perms: dict[str, Permission]) -> Group:
    stmt = select(Group).where(Group.name == "admin").options(selectinload(Group.permissions))
    group = (await session.execute(stmt)).scalar_one_or_none()
    if group is None:
        group = Group(name="admin", description="Full administrative access")
        session.add(group)
    group.permissions = list(perms.values())
    await session.flush()
    return group


async def _ensure_superuser(session, admin_group: Group) -> User:
    email = os.environ.get("KOB_SEED_ADMIN_EMAIL", "admin@kob.local")
    password = os.environ.get("KOB_SEED_ADMIN_PASSWORD", "ChangeMe!2026")

    stmt = select(User).where(User.email == email).options(selectinload(User.groups))
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        print(f"  • created superuser {email!r}")  # noqa: T201
    else:
        print(f"  • superuser {email!r} already exists")  # noqa: T201

    if admin_group not in user.groups:
        user.groups.append(admin_group)

    await session.flush()
    return user


async def main() -> None:
    print("seeding KOB-ERP core data ...")  # noqa: T201
    async with session_factory() as session:
        try:
            perms = await _ensure_permissions(session)
            print(f"  • {len(perms)} permissions ensured")  # noqa: T201
            admin_group = await _ensure_admin_group(session, perms)
            print(f"  • group {admin_group.name!r} ensured with {len(admin_group.permissions)} perms")  # noqa: T201
            await _ensure_superuser(session, admin_group)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    print("seed complete.")  # noqa: T201


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
