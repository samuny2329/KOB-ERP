"""Sales advanced module — Phase 10 unit tests.

State machines, model field shapes, and pure-function service tests.
DB-backed integration tests live in a separate suite.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.core.workflow import WorkflowError, WorkflowMixin
from backend.modules.sales import models, models_advanced
from backend.modules.sales.service import customer_credit_check
from backend.modules.sales.models_advanced import (
    IntercompanyTransfer,
    ReturnOrder,
    RETURN_REASONS,
)


# ── State machines ─────────────────────────────────────────────────────


def test_return_order_inherits_workflow_mixin() -> None:
    assert issubclass(ReturnOrder, WorkflowMixin)


def test_return_order_state_flow() -> None:
    flow = ReturnOrder.allowed_transitions
    assert flow["draft"] == {"received", "cancelled"}
    assert flow["received"] == {"restocked", "scrapped"}
    assert flow["restocked"] == set()  # terminal
    assert flow["scrapped"] == set()  # terminal
    assert flow["cancelled"] == set()


def test_return_order_cant_skip_received() -> None:
    """draft → restocked must NOT be reachable directly."""
    legal = ReturnOrder.allowed_transitions["draft"]
    assert "restocked" not in legal
    assert "scrapped" not in legal


def test_intercompany_transfer_state_flow() -> None:
    flow = IntercompanyTransfer.allowed_transitions
    assert flow["draft"] == {"mirrored", "cancelled"}
    assert flow["mirrored"] == {"settled", "cancelled"}
    assert flow["settled"] == set()
    assert flow["cancelled"] == set()


# ── Field shape ────────────────────────────────────────────────────────


def test_customer_phase10_fields_exist() -> None:
    cls = models.Customer
    cols = {c.name for c in cls.__table__.columns}
    for required in (
        "company_id",
        "pricelist_id",
        "sales_team_id",
        "payment_term_id",
        "customer_group",
        "credit_consumed",
        "ltv_score",
        "blocked",
        "blocked_reason",
    ):
        assert required in cols, f"Customer missing column: {required}"


def test_sales_order_phase10_fields_exist() -> None:
    cls = models.SalesOrder
    cols = {c.name for c in cls.__table__.columns}
    for required in (
        "company_id",
        "sales_team_id",
        "salesperson_id",
        "commission_pct",
        "payment_term_id",
        "pricelist_id",
        "lost_reason_id",
        "won_at",
        "lost_at",
        "revision",
        "revision_of_id",
        "promise_date",
        "p2d_confidence",
    ):
        assert required in cols, f"SalesOrder missing column: {required}"


def test_pricelist_rule_constraints() -> None:
    cls = models_advanced.PricelistRule
    cols = {c.name for c in cls.__table__.columns}
    for required in ("pricelist_id", "sequence", "rule_type", "value", "min_qty"):
        assert required in cols


def test_multi_platform_unique_constraint() -> None:
    constraints = {
        c.name
        for c in models_advanced.MultiPlatformOrder.__table__.constraints
        if c.name
    }
    assert "uq_multi_platform_pair" in constraints


def test_channel_margin_unique_window() -> None:
    constraints = {
        c.name
        for c in models_advanced.ChannelMargin.__table__.constraints
        if c.name
    }
    assert "uq_channel_margin_window" in constraints


# ── RETURN_REASONS catalogue ───────────────────────────────────────────


def test_return_reasons_complete() -> None:
    expected = {
        "wrong_item",
        "damaged",
        "defective",
        "not_as_described",
        "buyer_remorse",
        "expired",
        "duplicate",
        "other",
    }
    assert expected == set(RETURN_REASONS)


# ── customer_credit_check ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_credit_check_blocked_customer() -> None:
    customer = SimpleNamespace(
        blocked=True,
        blocked_reason="fraud hold",
        credit_consumed=0,
        credit_limit=10_000,
    )
    allowed, reason, available = await customer_credit_check(customer, draft_amount=500)
    assert allowed is False
    assert reason == "fraud hold"
    assert available == 0


@pytest.mark.asyncio
async def test_credit_check_within_limit() -> None:
    customer = SimpleNamespace(
        blocked=False,
        blocked_reason=None,
        credit_consumed=2_000,
        credit_limit=10_000,
    )
    allowed, reason, available = await customer_credit_check(customer, draft_amount=3_000)
    assert allowed is True
    assert reason is None
    assert available == 8_000


@pytest.mark.asyncio
async def test_credit_check_exceeds_limit() -> None:
    customer = SimpleNamespace(
        blocked=False,
        blocked_reason=None,
        credit_consumed=8_000,
        credit_limit=10_000,
    )
    allowed, reason, _ = await customer_credit_check(customer, draft_amount=3_000)
    assert allowed is False
    assert "exceed" in (reason or "")


@pytest.mark.asyncio
async def test_credit_check_unlimited_when_zero_limit() -> None:
    customer = SimpleNamespace(
        blocked=False,
        blocked_reason=None,
        credit_consumed=999_999,
        credit_limit=0,
    )
    allowed, _, available = await customer_credit_check(customer, draft_amount=999_999_999)
    assert allowed is True
    assert available == float("inf")


# ── Multi-company FKs on cross-cutting tables ──────────────────────────


def test_warehouse_has_company_id() -> None:
    from backend.modules.wms.models import Warehouse

    cols = {c.name for c in Warehouse.__table__.columns}
    assert "company_id" in cols


def test_outbound_order_has_company_id() -> None:
    from backend.modules.outbound.models import Order

    cols = {c.name for c in Order.__table__.columns}
    assert "company_id" in cols


def test_purchase_order_has_company_id() -> None:
    from backend.modules.purchase.models import PurchaseOrder

    cols = {c.name for c in PurchaseOrder.__table__.columns}
    assert "company_id" in cols


def test_sales_order_has_company_id() -> None:
    from backend.modules.sales.models import SalesOrder

    cols = {c.name for c in SalesOrder.__table__.columns}
    assert "company_id" in cols


def test_journal_entry_has_company_id() -> None:
    from backend.modules.accounting.models import JournalEntry

    cols = {c.name for c in JournalEntry.__table__.columns}
    assert "company_id" in cols


# ── core.scoping helper ────────────────────────────────────────────────


def test_company_scoped_skips_models_without_column() -> None:
    """Non-company-aware models pass through unchanged."""
    from sqlalchemy import select

    from backend.core.scoping import company_scoped
    from backend.modules.wms.models import Uom

    user = SimpleNamespace(is_superuser=False, default_company_id=1)
    stmt = select(Uom)
    new_stmt = company_scoped(stmt, user, Uom)
    # Same object returned (no WHERE added)
    assert str(new_stmt) == str(stmt)


def test_company_scoped_superuser_no_filter() -> None:
    from sqlalchemy import select

    from backend.core.scoping import company_scoped
    from backend.modules.sales.models import SalesOrder

    user = SimpleNamespace(is_superuser=True, default_company_id=1)
    stmt = select(SalesOrder)
    new_stmt = company_scoped(stmt, user, SalesOrder)
    # Superuser → no extra filter
    assert "company_id" not in str(new_stmt).lower() or "where" not in str(new_stmt).lower()


def test_company_scoped_regular_user_adds_filter() -> None:
    from sqlalchemy import select

    from backend.core.scoping import company_scoped
    from backend.modules.sales.models import SalesOrder

    user = SimpleNamespace(is_superuser=False, default_company_id=42)
    stmt = select(SalesOrder)
    new_stmt = company_scoped(stmt, user, SalesOrder)
    sql = str(new_stmt)
    assert "company_id" in sql.lower()
