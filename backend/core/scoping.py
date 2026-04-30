"""Multi-company query scoping helper.

Apply this to list endpoints so non-superusers only see records belonging
to their currently active company.  Records with ``company_id IS NULL``
are treated as global (visible to everyone).
"""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.sql import Select

from backend.core.models import User


def company_scoped(
    stmt: Select,
    user: User,
    model_class,
    column_name: str = "company_id",
    override_company_id: int | None = None,
) -> Select:
    """Add a ``company_id`` filter to ``stmt`` based on the requesting user.

    Rules:
      - Superusers see everything (no filter applied).
      - If ``override_company_id`` is set (and user is superuser), filter
        by that — useful for `?company_id=` admin lookups.
      - Otherwise: rows with company_id == user.default_company_id OR
        rows with company_id IS NULL (global / cross-company shared).
      - If the model doesn't have the column, return ``stmt`` unchanged.

    Usage::

        stmt = select(Warehouse).where(Warehouse.deleted_at.is_(None))
        stmt = company_scoped(stmt, current_user, Warehouse)
    """
    column = getattr(model_class, column_name, None)
    if column is None:
        return stmt

    if user.is_superuser:
        if override_company_id is not None:
            return stmt.where(column == override_company_id)
        return stmt

    return stmt.where(or_(column == user.default_company_id, column.is_(None)))


def assign_default_company(record, user: User, column_name: str = "company_id") -> None:
    """Stamp ``user.default_company_id`` onto a record if it lacks one.

    Idempotent — does nothing if the record already has a company set or
    the model doesn't have the column.  Use right after constructing a
    new domain object inside a route handler.
    """
    if not hasattr(record, column_name):
        return
    if getattr(record, column_name) is not None:
        return
    if user.default_company_id is None:
        return
    setattr(record, column_name, user.default_company_id)
