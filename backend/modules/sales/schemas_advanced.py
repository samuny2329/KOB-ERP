"""Pydantic schemas for advanced sales models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SalesTeamCreate(BaseModel):
    code: str
    name: str
    manager_id: int | None = None
    active: bool = True


class SalesTeamRead(SalesTeamCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class SalesPriceRuleCreate(BaseModel):
    pricelist_id: int
    product_id: int | None = None
    product_category: str | None = None
    min_qty: float = 0
    price: float
    date_from: date | None = None
    date_to: date | None = None


class SalesPriceRuleRead(SalesPriceRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SalesPricelistCreate(BaseModel):
    name: str
    currency: str = "THB"
    active: bool = True
    company_id: int | None = None


class SalesPricelistRead(SalesPricelistCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class BestPriceResult(BaseModel):
    product_id: int
    qty: float
    unit_price: float
    pricelist_id: int | None = None
    rule_id: int | None = None


class RmaLineCreate(BaseModel):
    product_id: int
    qty_requested: float
    return_reason: str | None = None


class RmaLineRead(RmaLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    qty_received: float


class RmaOrderCreate(BaseModel):
    number: str
    so_id: int
    reason: str | None = None
    lines: list[RmaLineCreate] = []


class RmaOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    so_id: int
    state: str
    reason: str | None
    confirmed_at: datetime | None
    received_at: datetime | None
    done_at: datetime | None
    created_at: datetime
    lines: list[RmaLineRead] = []


class QuotationTemplateLineCreate(BaseModel):
    product_id: int
    qty: float = 1
    unit_price: float
    discount_pct: float = 0


class QuotationTemplateLineRead(QuotationTemplateLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class QuotationTemplateCreate(BaseModel):
    name: str
    active: bool = True
    lines: list[QuotationTemplateLineCreate] = []


class QuotationTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    active: bool
    created_at: datetime
    lines: list[QuotationTemplateLineRead] = []


class PlatformFeeRuleCreate(BaseModel):
    platform: str
    fee_pct: float
    effective_from: date
    effective_to: date | None = None
    company_id: int | None = None


class PlatformFeeRuleRead(PlatformFeeRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class SoMarginLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    so_line_id: int
    cogs: float
    platform_fee: float
    gross_margin: float
    margin_pct: float
    captured_at: datetime


class EtaxInvoiceRefCreate(BaseModel):
    so_id: int
    etax_number: str
    issued_at: datetime
    revenue_dept_ref: str | None = None
    company_id: int | None = None


class EtaxInvoiceRefRead(EtaxInvoiceRefCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class IntercompanySalesOrderCreate(BaseModel):
    so_id: int
    to_company_id: int


class IntercompanySalesOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_company_id: int
    to_company_id: int
    so_id: int
    po_id: int | None
    transfer_price_rule_id: int | None
    status: str
    created_at: datetime


class ApplyPricelistPayload(BaseModel):
    pricelist_id: int


class MarginBreakdown(BaseModel):
    so_line_id: int
    revenue: float
    cogs: float
    platform_fee: float
    gross_margin: float
    margin_pct: float
