"""Pydantic schemas for sales advanced features."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Sales team ─────────────────────────────────────────────────────────


class SalesTeamCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    company_id: int | None = None
    manager_id: int | None = None
    default_commission_pct: float = 0
    target_revenue: float = 0


class SalesTeamRead(_ORM):
    id: int
    code: str
    name: str
    company_id: int | None
    manager_id: int | None
    default_commission_pct: float
    target_revenue: float
    active: bool


# ── Pricelist ──────────────────────────────────────────────────────────


PricelistBase = Literal["list_price", "standard_cost", "other_pricelist"]
RuleType = Literal["fixed", "discount_pct", "formula"]


class PricelistCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    company_id: int | None = None
    currency: str = "THB"
    base: PricelistBase = "list_price"
    customer_group: str | None = None


class PricelistRead(_ORM):
    id: int
    code: str
    name: str
    company_id: int | None
    currency: str
    base: str
    customer_group: str | None
    active: bool


class PricelistRuleCreate(BaseModel):
    pricelist_id: int
    sequence: int = 10
    product_id: int | None = None
    product_category_id: int | None = None
    min_qty: float = 0
    rule_type: RuleType = "discount_pct"
    value: float = 0
    valid_from: date | None = None
    valid_to: date | None = None


class PricelistRuleRead(_ORM):
    id: int
    pricelist_id: int
    sequence: int
    product_id: int | None
    product_category_id: int | None
    min_qty: float
    rule_type: str
    value: float
    valid_from: date | None
    valid_to: date | None
    active: bool


# ── Lost reason ────────────────────────────────────────────────────────


class LostReasonCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    sequence: int = 10


class LostReasonRead(_ORM):
    id: int
    code: str
    name: str
    sequence: int
    active: bool


# ── Returns ────────────────────────────────────────────────────────────


ReturnReason = Literal[
    "wrong_item",
    "damaged",
    "defective",
    "not_as_described",
    "buyer_remorse",
    "expired",
    "duplicate",
    "other",
]


class ReturnLineCreate(BaseModel):
    so_line_id: int | None = None
    product_id: int
    qty_returned: float = Field(gt=0)
    reason_code: ReturnReason = "other"
    reason_note: str | None = None
    refund_amount: float = 0
    lot_id: int | None = None


class ReturnLineRead(_ORM):
    id: int
    return_order_id: int
    so_line_id: int | None
    product_id: int
    qty_returned: float
    qty_restocked: float
    qty_scrapped: float
    reason_code: str
    reason_note: str | None
    refund_amount: float
    lot_id: int | None


class ReturnOrderCreate(BaseModel):
    ref: str = Field(min_length=1, max_length=40)
    sales_order_id: int
    company_id: int | None = None
    receipt_location_id: int | None = None
    note: str | None = None
    lines: list[ReturnLineCreate] = Field(default_factory=list, min_length=1)


class ReturnOrderRead(_ORM):
    id: int
    ref: str
    sales_order_id: int
    company_id: int | None
    state: str
    requested_at: datetime
    received_at: datetime | None
    completed_at: datetime | None
    receipt_location_id: int | None
    refund_amount: float
    note: str | None
    lines: list[ReturnLineRead] = Field(default_factory=list)


# ── Multi-platform ─────────────────────────────────────────────────────


class MultiPlatformOrderCreate(BaseModel):
    sales_order_id: int
    platform_order_id: int
    commission_pct: float = 0
    commission_deducted: float = 0
    shipping_subsidy: float = 0
    note: str | None = None


class MultiPlatformOrderRead(_ORM):
    id: int
    sales_order_id: int
    platform_order_id: int
    commission_pct: float
    commission_deducted: float
    shipping_subsidy: float
    note: str | None


# ── Channel margin ─────────────────────────────────────────────────────


class ChannelMarginRead(_ORM):
    id: int
    company_id: int | None
    channel: str
    period_start: date
    period_end: date
    gross_revenue: float
    cogs: float
    platform_fees: float
    shipping_cost: float
    return_amount: float
    net_margin: float
    margin_pct: float
    order_count: int
    refreshed_at: datetime | None


# ── Customer LTV ───────────────────────────────────────────────────────


class CustomerLtvSnapshotRead(_ORM):
    id: int
    customer_id: int
    snapshot_date: date
    revenue_90d: float
    order_count_90d: int
    repeat_rate: float
    return_rate: float
    avg_order_value: float
    score: float


# ── Promise to deliver / credit check ──────────────────────────────────


class PromiseToDeliverResult(BaseModel):
    promise_date: date
    confidence: float
    available_warehouse_id: int | None
    note: str | None = None


class CreditCheckResult(BaseModel):
    allowed: bool
    reason: str | None = None
    credit_consumed: float
    credit_limit: float
    available: float


# ── Intercompany ───────────────────────────────────────────────────────


class IntercompanyTransferCreate(BaseModel):
    sales_order_id: int
    so_company_id: int
    fulfillment_company_id: int
    transfer_pricing_method: Literal["cost_plus", "fixed", "market"] = "cost_plus"
    transfer_pricing_pct: float = 0
    note: str | None = None


class IntercompanyTransferRead(_ORM):
    id: int
    sales_order_id: int
    so_company_id: int
    fulfillment_company_id: int
    state: str
    mirror_po_id: int | None
    transfer_amount: float
    transfer_pricing_method: str
    transfer_pricing_pct: float
    settled_at: datetime | None
    note: str | None
