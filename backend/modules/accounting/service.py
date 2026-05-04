"""Accounting business logic — posting, reconciliation, Thai VAT/PND1 reports."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.workflow import WorkflowError
from backend.modules.accounting.models import JournalEntry, JournalEntryLine
from backend.modules.accounting.models_advanced import (
    AccountingClosingEntry,
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


# ── Journal Entry Posting ──────────────────────────────────────────────


async def post_journal_entry(session: AsyncSession, entry: JournalEntry) -> JournalEntry:
    """draft → posted.  Validates debit == credit balance."""
    lines_result = await session.execute(
        select(JournalEntryLine).where(JournalEntryLine.entry_id == entry.id)
    )
    lines = list(lines_result.scalars().all())
    total_debit = sum(float(l.debit) for l in lines)
    total_credit = sum(float(l.credit) for l in lines)
    if round(abs(total_debit - total_credit), 2) > 0.01:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"journal entry is not balanced: debit={total_debit:.2f} credit={total_credit:.2f}",
        )
    try:
        entry.transition("posted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    entry.posted_at = datetime.now(UTC)
    await session.flush()
    return entry


# ── Invoice Posting ────────────────────────────────────────────────────


async def post_invoice(session: AsyncSession, invoice: CustomerInvoice) -> CustomerInvoice:
    """draft → posted.  Recomputes totals, stamps posted_at."""
    lines_result = await session.execute(
        select(CustomerInvoiceLine).where(CustomerInvoiceLine.invoice_id == invoice.id)
    )
    lines = list(lines_result.scalars().all())
    subtotal = sum(float(l.subtotal) for l in lines)
    tax_amount = sum(float(l.tax_amount) for l in lines)
    total = subtotal + tax_amount

    invoice.subtotal = round(subtotal, 2)
    invoice.tax_amount = round(tax_amount, 2)
    invoice.total = round(total, 2)
    invoice.amount_due = round(total - float(invoice.amount_paid), 2)

    try:
        invoice.transition("posted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    invoice.posted_at = datetime.now(UTC)
    await session.flush()
    return invoice


async def post_vendor_bill(session: AsyncSession, bill: VendorBill) -> VendorBill:
    """draft → posted.  Recomputes totals net of WHT."""
    lines_result = await session.execute(
        select(VendorBillLine).where(VendorBillLine.bill_id == bill.id)
    )
    lines = list(lines_result.scalars().all())
    subtotal = sum(float(l.subtotal) for l in lines)
    tax_amount = sum(float(l.tax_amount) for l in lines)
    total = round(subtotal + tax_amount - float(bill.wht_amount), 2)

    bill.subtotal = round(subtotal, 2)
    bill.tax_amount = round(tax_amount, 2)
    bill.total = total
    bill.amount_due = round(total - float(bill.amount_paid), 2)

    try:
        bill.transition("posted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    bill.posted_at = datetime.now(UTC)
    await session.flush()
    return bill


# ── Thai VAT Report ────────────────────────────────────────────────────


async def compute_vat_report(
    session: AsyncSession, company_id: int, period_month: int, period_year: int
) -> ThaiVatReport:
    """Aggregate output/input VAT from posted invoices and bills for the period."""
    from sqlalchemy import extract

    # Output VAT from customer invoices
    inv_result = await session.execute(
        select(func.coalesce(func.sum(CustomerInvoice.tax_amount), 0)).where(
            CustomerInvoice.company_id == company_id,
            CustomerInvoice.state == "posted",
            CustomerInvoice.deleted_at.is_(None),
            extract("month", CustomerInvoice.invoice_date) == period_month,
            extract("year", CustomerInvoice.invoice_date) == period_year,
        )
    )
    output_vat = float(inv_result.scalar() or 0)

    # Input VAT from vendor bills
    bill_result = await session.execute(
        select(func.coalesce(func.sum(VendorBill.tax_amount), 0)).where(
            VendorBill.company_id == company_id,
            VendorBill.state == "posted",
            VendorBill.deleted_at.is_(None),
            extract("month", VendorBill.bill_date) == period_month,
            extract("year", VendorBill.bill_date) == period_year,
        )
    )
    input_vat = float(bill_result.scalar() or 0)

    net_vat = round(output_vat - input_vat, 2)

    # Upsert
    existing = (
        await session.execute(
            select(ThaiVatReport).where(
                ThaiVatReport.company_id == company_id,
                ThaiVatReport.period_month == period_month,
                ThaiVatReport.period_year == period_year,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.total_vat_output = round(output_vat, 2)
        existing.total_vat_input = round(input_vat, 2)
        existing.net_vat = net_vat
        await session.flush()
        return existing

    report = ThaiVatReport(
        company_id=company_id,
        period_month=period_month,
        period_year=period_year,
        total_vat_output=round(output_vat, 2),
        total_vat_input=round(input_vat, 2),
        net_vat=net_vat,
        status="draft",
    )
    session.add(report)
    await session.flush()
    return report


# ── Invoice Line Computation (pure) ────────────────────────────────────


def compute_invoice_line(
    qty: float, unit_price: float, discount_pct: float = 0.0, tax_rate: float = 7.0
) -> dict[str, float]:
    """Pure function — compute subtotal and tax for one invoice line."""
    net = qty * unit_price * (1 - discount_pct / 100)
    tax = round(net * tax_rate / 100, 2)
    return {
        "subtotal": round(net, 2),
        "tax_amount": tax,
        "total": round(net + tax, 2),
    }


# ── Bank Statement Reconciliation ──────────────────────────────────────


async def post_bank_statement(
    session: AsyncSession, statement: BankStatement
) -> BankStatement:
    """draft → posted."""
    try:
        statement.transition("posted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.flush()
    return statement


async def reconcile_statement_line(
    session: AsyncSession,
    line: BankStatementLine,
    journal_entry_id: int,
) -> BankStatementLine:
    """Mark a bank statement line as reconciled to a journal entry."""
    line.reconciled = True
    line.journal_entry_id = journal_entry_id
    await session.flush()
    # If all lines are reconciled → auto-transition statement to reconciled
    stmt = await session.get(BankStatement, line.statement_id)
    if stmt and stmt.state == "posted":
        all_lines_result = await session.execute(
            select(BankStatementLine).where(BankStatementLine.statement_id == stmt.id)
        )
        all_lines = list(all_lines_result.scalars().all())
        if all(l.reconciled for l in all_lines):
            stmt.transition("reconciled")
            await session.flush()
    return line


# ── Fiscal Year Closing ────────────────────────────────────────────────


async def close_fiscal_year(
    session: AsyncSession,
    fiscal_year_id: int,
    company_id: int,
    closing_entry_id: int | None = None,
) -> AccountingClosingEntry:
    """Create or update the year-end closing record and lock the fiscal year."""
    fy = await session.get(FiscalYear, fiscal_year_id)
    if not fy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "fiscal year not found")
    if fy.state == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "fiscal year already closed")

    existing = (
        await session.execute(
            select(AccountingClosingEntry).where(
                AccountingClosingEntry.fiscal_year_id == fiscal_year_id,
                AccountingClosingEntry.company_id == company_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        closing = existing
    else:
        closing = AccountingClosingEntry(
            fiscal_year_id=fiscal_year_id,
            company_id=company_id,
            status="draft",
        )
        session.add(closing)

    closing.journal_entry_id = closing_entry_id
    closing.status = "closed"
    closing.closed_at = datetime.now(UTC)
    fy.state = "closed"
    await session.flush()
    return closing
