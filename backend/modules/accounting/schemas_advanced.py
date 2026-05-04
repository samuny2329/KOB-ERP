"""Pydantic schemas for advanced accounting models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class FiscalYearCreate(BaseModel):
    name: str
    date_from: date
    date_to: date
    company_id: int | None = None


class FiscalYearRead(FiscalYearCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    state: str
    created_at: datetime


class AnalyticAccountCreate(BaseModel):
    code: str
    name: str
    plan: str = "project"
    company_id: int | None = None
    active: bool = True


class AnalyticAccountRead(AnalyticAccountCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class BankStatementLineCreate(BaseModel):
    transaction_date: date
    name: str
    amount: float
    partner_type: str | None = None
    partner_id: int | None = None
    account_id: int | None = None


class BankStatementLineRead(BankStatementLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    statement_id: int
    reconciled: bool
    journal_entry_id: int | None


class BankStatementCreate(BaseModel):
    number: str
    journal_id: int
    statement_date: date
    balance_start: float = 0
    balance_end: float = 0
    company_id: int | None = None
    lines: list[BankStatementLineCreate] = []


class BankStatementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    journal_id: int
    state: str
    statement_date: date
    balance_start: float
    balance_end: float
    created_at: datetime
    lines: list[BankStatementLineRead] = []


class CustomerInvoiceLineCreate(BaseModel):
    product_id: int | None = None
    description: str
    qty: float = 1
    unit_price: float
    discount_pct: float = 0
    tax_rate: float = 7.0
    account_id: int | None = None
    analytic_account_id: int | None = None


class CustomerInvoiceLineRead(CustomerInvoiceLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tax_amount: float
    subtotal: float


class CustomerInvoiceCreate(BaseModel):
    number: str
    customer_id: int
    so_id: int | None = None
    invoice_date: date
    due_date: date | None = None
    currency: str = "THB"
    company_id: int | None = None
    lines: list[CustomerInvoiceLineCreate] = []


class CustomerInvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    customer_id: int
    so_id: int | None
    state: str
    invoice_date: date
    due_date: date | None
    currency: str
    subtotal: float
    tax_amount: float
    total: float
    amount_paid: float
    amount_due: float
    posted_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    lines: list[CustomerInvoiceLineRead] = []


class VendorBillLineCreate(BaseModel):
    product_id: int | None = None
    description: str
    qty: float = 1
    unit_price: float
    tax_rate: float = 7.0
    account_id: int | None = None
    analytic_account_id: int | None = None


class VendorBillLineRead(VendorBillLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tax_amount: float
    subtotal: float


class VendorBillCreate(BaseModel):
    number: str
    vendor_id: int
    po_id: int | None = None
    bill_date: date
    due_date: date | None = None
    currency: str = "THB"
    wht_amount: float = 0
    company_id: int | None = None
    lines: list[VendorBillLineCreate] = []


class VendorBillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    vendor_id: int
    po_id: int | None
    state: str
    bill_date: date
    due_date: date | None
    currency: str
    subtotal: float
    tax_amount: float
    wht_amount: float
    total: float
    amount_paid: float
    amount_due: float
    posted_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    lines: list[VendorBillLineRead] = []


class ThaiVatReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    period_month: int
    period_year: int
    total_vat_output: float
    total_vat_input: float
    net_vat: float
    status: str
    filed_at: datetime | None
    rd_ref: str | None


class ThaiPnd1ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    period_month: int
    period_year: int
    total_employees: int
    total_income: float
    total_wht: float
    status: str
    filed_at: datetime | None


class VatReportComputePayload(BaseModel):
    company_id: int
    period_month: int
    period_year: int


class InvoiceLineComputed(BaseModel):
    subtotal: float
    tax_amount: float
    total: float


class ReconcilePayload(BaseModel):
    journal_entry_id: int


class CloseFiscalYearPayload(BaseModel):
    fiscal_year_id: int
    company_id: int
    closing_entry_id: int | None = None
