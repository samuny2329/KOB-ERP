"""Advanced accounting routes — invoices, bills, analytics, bank rec, Thai tax reports."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.db import SessionDep
from backend.modules.accounting.models_advanced import (
    AnalyticAccount,
    BankStatement,
    BankStatementLine,
    CustomerInvoice,
    CustomerInvoiceLine,
    FiscalYear,
    ThaiPnd1Report,
    ThaiVatReport,
    VendorBill,
    VendorBillLine,
)
from backend.modules.accounting.schemas_advanced import (
    AnalyticAccountCreate,
    AnalyticAccountRead,
    BankStatementCreate,
    BankStatementRead,
    CloseFiscalYearPayload,
    CustomerInvoiceCreate,
    CustomerInvoiceRead,
    FiscalYearCreate,
    FiscalYearRead,
    InvoiceLineComputed,
    ReconcilePayload,
    ThaiPnd1ReportRead,
    ThaiVatReportRead,
    VatReportComputePayload,
    VendorBillCreate,
    VendorBillRead,
)
from backend.modules.accounting.service import (
    close_fiscal_year,
    compute_invoice_line,
    compute_vat_report,
    post_bank_statement,
    post_invoice,
    post_journal_entry,
    post_vendor_bill,
    reconcile_statement_line,
)
from backend.modules.accounting.models import JournalEntry

router = APIRouter(prefix="/accounting", tags=["accounting-advanced"])


# ── Fiscal Years ───────────────────────────────────────────────────────


@router.post("/fiscal-years", response_model=FiscalYearRead, status_code=status.HTTP_201_CREATED)
async def create_fiscal_year(payload: FiscalYearCreate, session: SessionDep):
    fy = FiscalYear(**payload.model_dump(), state="open")
    session.add(fy)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "fiscal year already exists for this company/name")
    return fy


@router.get("/fiscal-years", response_model=list[FiscalYearRead])
async def list_fiscal_years(session: SessionDep, company_id: int | None = None):
    stmt = select(FiscalYear).where(FiscalYear.deleted_at.is_(None))
    if company_id:
        stmt = stmt.where(FiscalYear.company_id == company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/fiscal-years/close")
async def close_fy(payload: CloseFiscalYearPayload, session: SessionDep):
    closing = await close_fiscal_year(session, payload.fiscal_year_id, payload.company_id, payload.closing_entry_id)
    return {"id": closing.id, "status": closing.status, "closed_at": closing.closed_at}


# ── Analytic Accounts ──────────────────────────────────────────────────


@router.post("/analytic-accounts", response_model=AnalyticAccountRead, status_code=status.HTTP_201_CREATED)
async def create_analytic_account(payload: AnalyticAccountCreate, session: SessionDep):
    acct = AnalyticAccount(**payload.model_dump())
    session.add(acct)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "analytic account code already exists in this company")
    return acct


@router.get("/analytic-accounts", response_model=list[AnalyticAccountRead])
async def list_analytic_accounts(session: SessionDep, plan: str | None = None):
    stmt = select(AnalyticAccount).where(AnalyticAccount.deleted_at.is_(None), AnalyticAccount.active.is_(True))
    if plan:
        stmt = stmt.where(AnalyticAccount.plan == plan)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Journal Entry Enhanced ─────────────────────────────────────────────


@router.post("/journal-entries/{entry_id}/post")
async def post_entry(entry_id: int, session: SessionDep):
    entry = await session.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "journal entry not found")
    await post_journal_entry(session, entry)
    return {"id": entry.id, "state": entry.state, "posted_at": entry.posted_at}


# ── Bank Statements ────────────────────────────────────────────────────


@router.post("/bank-statements", response_model=BankStatementRead, status_code=status.HTTP_201_CREATED)
async def create_bank_statement(payload: BankStatementCreate, session: SessionDep):
    bs = BankStatement(
        number=payload.number, journal_id=payload.journal_id,
        statement_date=payload.statement_date, balance_start=payload.balance_start,
        balance_end=payload.balance_end, company_id=payload.company_id, state="draft",
    )
    session.add(bs)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "bank statement number already exists")
    for line in payload.lines:
        session.add(BankStatementLine(statement_id=bs.id, **line.model_dump()))
    await session.flush()
    await session.refresh(bs, ["lines"])
    return bs


@router.get("/bank-statements", response_model=list[BankStatementRead])
async def list_bank_statements(session: SessionDep, journal_id: int | None = None):
    stmt = select(BankStatement).where(BankStatement.deleted_at.is_(None)).options(
        selectinload(BankStatement.lines)
    )
    if journal_id:
        stmt = stmt.where(BankStatement.journal_id == journal_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/bank-statements/{bs_id}/post", response_model=BankStatementRead)
async def post_statement(bs_id: int, session: SessionDep):
    bs = await session.get(BankStatement, bs_id, options=[selectinload(BankStatement.lines)])
    if not bs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bank statement not found")
    return await post_bank_statement(session, bs)


@router.post("/bank-statements/{bs_id}/lines/{line_id}/reconcile")
async def reconcile_line(bs_id: int, line_id: int, payload: ReconcilePayload, session: SessionDep):
    line = await session.get(BankStatementLine, line_id)
    if not line or line.statement_id != bs_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "statement line not found")
    await reconcile_statement_line(session, line, payload.journal_entry_id)
    return {"id": line.id, "reconciled": line.reconciled}


# ── Customer Invoices ──────────────────────────────────────────────────


@router.post("/invoices", response_model=CustomerInvoiceRead, status_code=status.HTTP_201_CREATED)
async def create_invoice(payload: CustomerInvoiceCreate, session: SessionDep):
    invoice = CustomerInvoice(
        number=payload.number, customer_id=payload.customer_id, so_id=payload.so_id,
        invoice_date=payload.invoice_date, due_date=payload.due_date,
        currency=payload.currency, company_id=payload.company_id, state="draft",
    )
    session.add(invoice)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "invoice number already exists")
    for line in payload.lines:
        computed = compute_invoice_line(line.qty, line.unit_price, line.discount_pct, line.tax_rate)
        session.add(CustomerInvoiceLine(
            invoice_id=invoice.id,
            product_id=line.product_id,
            description=line.description,
            qty=line.qty,
            unit_price=line.unit_price,
            discount_pct=line.discount_pct,
            tax_rate=line.tax_rate,
            tax_amount=computed["tax_amount"],
            subtotal=computed["subtotal"],
            account_id=line.account_id,
            analytic_account_id=line.analytic_account_id,
        ))
    await session.flush()
    await session.refresh(invoice, ["lines"])
    return invoice


@router.get("/invoices", response_model=list[CustomerInvoiceRead])
async def list_invoices(session: SessionDep, customer_id: int | None = None, state: str | None = None):
    stmt = select(CustomerInvoice).where(CustomerInvoice.deleted_at.is_(None)).options(
        selectinload(CustomerInvoice.lines)
    )
    if customer_id:
        stmt = stmt.where(CustomerInvoice.customer_id == customer_id)
    if state:
        stmt = stmt.where(CustomerInvoice.state == state)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/invoices/{invoice_id}/post", response_model=CustomerInvoiceRead)
async def post_invoice_endpoint(invoice_id: int, session: SessionDep):
    invoice = await session.get(CustomerInvoice, invoice_id, options=[selectinload(CustomerInvoice.lines)])
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    return await post_invoice(session, invoice)


@router.post("/invoices/{invoice_id}/pay")
async def mark_invoice_paid(invoice_id: int, session: SessionDep):
    invoice = await session.get(CustomerInvoice, invoice_id)
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    from backend.core.workflow import WorkflowError
    from datetime import UTC, datetime
    try:
        invoice.transition("paid")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    invoice.amount_paid = float(invoice.total)
    invoice.amount_due = 0
    invoice.paid_at = datetime.now(UTC)
    await session.flush()
    return {"id": invoice.id, "state": invoice.state}


# ── Vendor Bills ───────────────────────────────────────────────────────


@router.post("/bills", response_model=VendorBillRead, status_code=status.HTTP_201_CREATED)
async def create_bill(payload: VendorBillCreate, session: SessionDep):
    bill = VendorBill(
        number=payload.number, vendor_id=payload.vendor_id, po_id=payload.po_id,
        bill_date=payload.bill_date, due_date=payload.due_date,
        currency=payload.currency, wht_amount=payload.wht_amount,
        company_id=payload.company_id, state="draft",
    )
    session.add(bill)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "bill number already exists")
    for line in payload.lines:
        computed = compute_invoice_line(line.qty, line.unit_price, 0, line.tax_rate)
        session.add(VendorBillLine(
            bill_id=bill.id,
            product_id=line.product_id,
            description=line.description,
            qty=line.qty,
            unit_price=line.unit_price,
            tax_rate=line.tax_rate,
            tax_amount=computed["tax_amount"],
            subtotal=computed["subtotal"],
            account_id=line.account_id,
            analytic_account_id=line.analytic_account_id,
        ))
    await session.flush()
    await session.refresh(bill, ["lines"])
    return bill


@router.get("/bills", response_model=list[VendorBillRead])
async def list_bills(session: SessionDep, vendor_id: int | None = None, state: str | None = None):
    stmt = select(VendorBill).where(VendorBill.deleted_at.is_(None)).options(selectinload(VendorBill.lines))
    if vendor_id:
        stmt = stmt.where(VendorBill.vendor_id == vendor_id)
    if state:
        stmt = stmt.where(VendorBill.state == state)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/bills/{bill_id}/post", response_model=VendorBillRead)
async def post_bill_endpoint(bill_id: int, session: SessionDep):
    bill = await session.get(VendorBill, bill_id, options=[selectinload(VendorBill.lines)])
    if not bill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bill not found")
    return await post_vendor_bill(session, bill)


# ── Thai VAT Report ────────────────────────────────────────────────────


@router.post("/thai-vat-report/compute", response_model=ThaiVatReportRead)
async def compute_vat(payload: VatReportComputePayload, session: SessionDep):
    return await compute_vat_report(session, payload.company_id, payload.period_month, payload.period_year)


@router.get("/thai-vat-report", response_model=list[ThaiVatReportRead])
async def list_vat_reports(session: SessionDep, company_id: int | None = None):
    stmt = select(ThaiVatReport).where(ThaiVatReport.deleted_at.is_(None))
    if company_id:
        stmt = stmt.where(ThaiVatReport.company_id == company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/thai-vat-report/{report_id}/file")
async def file_vat_report(report_id: int, session: SessionDep, rd_ref: str | None = None):
    from datetime import UTC, datetime
    report = await session.get(ThaiVatReport, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "VAT report not found")
    report.status = "filed"
    report.filed_at = datetime.now(UTC)
    report.rd_ref = rd_ref
    await session.flush()
    return {"id": report.id, "status": report.status}


# ── Thai PND1 Report ───────────────────────────────────────────────────


@router.get("/thai-pnd1-report", response_model=list[ThaiPnd1ReportRead])
async def list_pnd1_reports(session: SessionDep, company_id: int | None = None):
    stmt = select(ThaiPnd1Report).where(ThaiPnd1Report.deleted_at.is_(None))
    if company_id:
        stmt = stmt.where(ThaiPnd1Report.company_id == company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Invoice Line Helper ────────────────────────────────────────────────


@router.get("/invoice-line/compute", response_model=InvoiceLineComputed)
async def compute_line(qty: float, unit_price: float, discount_pct: float = 0, tax_rate: float = 7.0):
    return compute_invoice_line(qty, unit_price, discount_pct, tax_rate)
