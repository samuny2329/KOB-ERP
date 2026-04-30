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
from backend.core.models import Company, Group, Permission, User
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
    # WMS master data
    _Perm("wms.warehouse", "read", "View warehouses"),
    _Perm("wms.warehouse", "write", "Create/edit warehouses"),
    _Perm("wms.location", "read", "View locations"),
    _Perm("wms.location", "write", "Create/edit locations"),
    _Perm("wms.zone", "read", "View zones"),
    _Perm("wms.zone", "write", "Create/edit zones"),
    _Perm("wms.uom", "read", "View units of measure"),
    _Perm("wms.uom", "write", "Create/edit units of measure"),
    _Perm("wms.product", "read", "View products"),
    _Perm("wms.product", "write", "Create/edit products"),
    _Perm("wms.lot", "read", "View lots / serials"),
    _Perm("wms.lot", "write", "Create/edit lots / serials"),
    # Inventory operations
    _Perm("inventory.quant", "read", "View on-hand stock"),
    _Perm("inventory.transfer", "read", "View transfers"),
    _Perm("inventory.transfer", "write", "Create/edit transfers"),
    _Perm("inventory.transfer", "confirm", "Confirm transfers"),
    _Perm("inventory.transfer", "done", "Validate (complete) transfers"),
    _Perm("inventory.transfer", "cancel", "Cancel transfers"),
    # WMS pick / pack master data (Phase 2b)
    _Perm("wms.rack", "read", "View racks"),
    _Perm("wms.rack", "write", "Create/edit racks"),
    _Perm("wms.pickface", "read", "View pickfaces"),
    _Perm("wms.pickface", "write", "Create/edit pickfaces"),
    _Perm("wms.courier", "read", "View couriers"),
    _Perm("wms.courier", "write", "Create/edit couriers"),
    # Outbound flow (Phase 2b)
    _Perm("outbound.order", "read", "View outbound orders"),
    _Perm("outbound.order", "write", "Create/edit outbound orders"),
    _Perm("outbound.order", "transition", "Move orders through pick/pack/ship states"),
    _Perm("outbound.dispatch", "read", "View dispatch batches"),
    _Perm("outbound.dispatch", "write", "Create/scan/finalise dispatch batches"),
    _Perm("core.activity_log", "read", "Read the hash-chained activity log"),
    # Cycle counts (Phase 2c)
    _Perm("inventory.count_session", "read", "View count sessions"),
    _Perm("inventory.count_session", "write", "Create / transition count sessions"),
    _Perm("inventory.count_task", "read", "View count tasks"),
    _Perm("inventory.count_task", "write", "Assign / transition count tasks"),
    _Perm("inventory.count_entry", "write", "Record count entries"),
    _Perm("inventory.count_adjustment", "approve", "Approve count adjustments"),
    # Quality (Phase 2c)
    _Perm("quality.check", "read", "View quality checks"),
    _Perm("quality.check", "write", "Create / transition quality checks"),
    _Perm("quality.defect", "write", "Record quality defects"),
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


async def _ensure_default_company(session) -> Company:
    """Create the headquarters company on first run."""
    stmt = select(Company).where(Company.code == "KOB")
    company = (await session.execute(stmt)).scalar_one_or_none()
    if company is None:
        company = Company(
            code="KOB",
            name="KOB Headquarters",
            legal_name="บริษัท คิสออฟบิวตี้ จำกัด",
            tax_id="0105560000000",
            address="Bangkok, Thailand",
            currency="THB",
            locale="th-TH",
            timezone="Asia/Bangkok",
            is_active=True,
        )
        session.add(company)
        await session.flush()
        print(f"  • created default company {company.code!r}")  # noqa: T201
    else:
        print(f"  • default company {company.code!r} already exists")  # noqa: T201
    return company


async def _ensure_admin_group(session, perms: dict[str, Permission]) -> Group:
    stmt = select(Group).where(Group.name == "admin").options(selectinload(Group.permissions))
    group = (await session.execute(stmt)).scalar_one_or_none()
    if group is None:
        group = Group(name="admin", description="Full administrative access")
        session.add(group)
    group.permissions = list(perms.values())
    await session.flush()
    return group


async def _ensure_superuser(session, admin_group: Group, default_company: Company) -> User:
    email = os.environ.get("KOB_SEED_ADMIN_EMAIL", "admin@koberp.co.th")
    password = os.environ.get("KOB_SEED_ADMIN_PASSWORD", "ChangeMe!2026")

    stmt = (
        select(User)
        .where(User.email == email)
        .options(selectinload(User.groups), selectinload(User.companies))
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
            default_company_id=default_company.id,
            preferred_locale="th-TH",
        )
        session.add(user)
        print(f"  • created superuser {email!r}")  # noqa: T201
    else:
        if user.default_company_id is None:
            user.default_company_id = default_company.id
        print(f"  • superuser {email!r} already exists")  # noqa: T201

    if admin_group not in user.groups:
        user.groups.append(admin_group)
    if default_company not in user.companies:
        user.companies.append(default_company)

    await session.flush()
    return user


async def main() -> None:
    print("seeding KOB-ERP core data ...")  # noqa: T201
    async with session_factory() as session:
        try:
            company = await _ensure_default_company(session)
            perms = await _ensure_permissions(session)
            print(f"  • {len(perms)} permissions ensured")  # noqa: T201
            admin_group = await _ensure_admin_group(session, perms)
            print(f"  • group {admin_group.name!r} ensured with {len(admin_group.permissions)} perms")  # noqa: T201
            await _ensure_superuser(session, admin_group, company)
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
