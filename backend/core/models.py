"""Core domain models — User, Group, Permission, AuditLog.

These live in the ``core`` schema and are referenced (FK) by every other
module.  They are kept in one file because they're tightly coupled and
small; module-specific models live in ``backend/modules/<name>/models.py``.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel, CoreModel
from backend.core.db import Base


# ── Association tables ─────────────────────────────────────────────────

user_group = Table(
    "user_group",
    Base.metadata,
    Column(
        "user_id",
        BigInteger,
        ForeignKey("core.user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "group_id",
        BigInteger,
        ForeignKey("core.group.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    schema="core",
)

group_permission = Table(
    "group_permission",
    Base.metadata,
    Column(
        "group_id",
        BigInteger,
        ForeignKey("core.group.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        BigInteger,
        ForeignKey("core.permission.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    schema="core",
)


# ── Models ─────────────────────────────────────────────────────────────


class User(CoreModel):
    """Application user — login + group membership."""

    __tablename__ = "user"
    __table_args__ = ({"schema": "core"},)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    groups: Mapped[list["Group"]] = relationship(
        secondary=user_group,
        back_populates="users",
        lazy="selectin",
    )


class Group(BaseModel):
    """A named bundle of permissions assigned to users.

    Lives in core schema.  Uses BaseModel (with audit fields) — created_by
    points to the User who created the group.
    """

    __tablename__ = "group"
    __table_args__ = ({"schema": "core"},)

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    users: Mapped[list["User"]] = relationship(
        secondary=user_group,
        back_populates="groups",
        lazy="selectin",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=group_permission,
        back_populates="groups",
        lazy="selectin",
    )


class Permission(BaseModel):
    """A (model, action) tuple — e.g. ('inventory.transfer', 'write').

    ``model`` is the dotted path of the protected resource; ``action`` is
    one of {read, write, create, delete, approve, ...}.  Uniqueness is
    enforced on the pair.
    """

    __tablename__ = "permission"
    __table_args__ = (
        UniqueConstraint("model", "action", name="uq_permission_model_action"),
        {"schema": "core"},
    )

    model: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    groups: Mapped[list["Group"]] = relationship(
        secondary=group_permission,
        back_populates="permissions",
        lazy="selectin",
    )

    @property
    def code(self) -> str:
        """Stable string identifier — ``"<model>:<action>"``."""
        return f"{self.model}:{self.action}"


class AuditLog(CoreModel):
    """Append-only log of write operations.

    Populated by ``backend.core.audit`` middleware.  ``before`` / ``after``
    are JSON snapshots of the affected record (only changed columns).
    """

    __tablename__ = "audit_log"
    __table_args__ = ({"schema": "core"},)

    actor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("core.user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    record_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)  # create/update/delete/state
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
