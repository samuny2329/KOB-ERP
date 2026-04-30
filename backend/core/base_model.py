"""Common mixins applied to every domain model.

Pulls Odoo-style audit fields into a reusable shape for SQLAlchemy 2.0:
- surrogate ``id``
- ``created_at`` / ``updated_at`` timestamps (UTC)
- ``created_by`` / ``updated_by`` foreign keys to ``core.user``
- soft-delete via ``deleted_at`` (set to NULL when active)
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from backend.core.db import Base


class TimestampMixin:
    """Adds created_at + updated_at columns, both UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds deleted_at column — NULL means active record."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class AuditMixin:
    """Adds created_by + updated_by foreign keys to ``core.user.id``.

    Applied to most domain models — but NOT to ``User`` itself (would
    create a circular FK at table-creation time).  See ``BaseModel`` for
    the standard combination.
    """

    @declared_attr
    @classmethod
    def created_by(cls) -> Mapped[int | None]:
        return mapped_column(
            BigInteger,
            ForeignKey("core.user.id", ondelete="SET NULL"),
            nullable=True,
        )

    @declared_attr
    @classmethod
    def updated_by(cls) -> Mapped[int | None]:
        return mapped_column(
            BigInteger,
            ForeignKey("core.user.id", ondelete="SET NULL"),
            nullable=True,
        )


class BaseModel(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Standard combination for domain models in non-core modules.

    Subclasses must declare their own ``__tablename__`` and
    ``__table_args__`` (including the schema).
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class CoreModel(Base, TimestampMixin, SoftDeleteMixin):
    """Like ``BaseModel`` but without AuditMixin — for ``core.user`` and
    other tables that must exist before AuditMixin's FK target.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
