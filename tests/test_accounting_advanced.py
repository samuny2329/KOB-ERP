"""Tests for advanced accounting models and service logic."""

import pytest

from backend.modules.accounting.models import Account, JournalEntry, JournalEntryLine
from backend.modules.accounting.models_advanced import (
    AccountingClosingEntry,
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
from backend.modules.accounting.service import compute_invoice_line


# ── Model structure ────────────────────────────────────────────────────


def test_account_new_fields():
    cols = {c.key for c in Account.__table__.columns}
    assert "company_id" in cols
    assert "analytic_tag" in cols


def test_journal_entry_state_machine():
    assert "posted" in JournalEntry.allowed_transitions["draft"]
    assert "cancelled" in JournalEntry.allowed_transitions["draft"]
    assert "cancelled" in JournalEntry.allowed_transitions["posted"]
    assert JournalEntry.allowed_transitions["cancelled"] == set()


def test_journal_entry_new_fields():
    cols = {c.key for c in JournalEntry.__table__.columns}
    assert "company_id" in cols
    assert "fiscal_year_id" in cols


def test_journal_entry_line_analytic():
    cols = {c.key for c in JournalEntryLine.__table__.columns}
    assert "analytic_account_id" in cols


def test_fiscal_year_unique_constraint():
    constraint_names = {c.name for c in FiscalYear.__table__.constraints}
    assert "uq_fiscal_year_name_company" in constraint_names


def test_analytic_account_unique_constraint():
    constraint_names = {c.name for c in AnalyticAccount.__table__.constraints}
    assert "uq_analytic_account_code_company" in constraint_names


def test_analytic_account_fields():
    cols = {c.key for c in AnalyticAccount.__table__.columns}
    assert "code" in cols
    assert "plan" in cols
    assert "active" in cols


def test_bank_statement_state_machine():
    assert "posted" in BankStatement.allowed_transitions["draft"]
    assert "reconciled" in BankStatement.allowed_transitions["posted"]
    assert "cancelled" in BankStatement.allowed_transitions["posted"]
    assert BankStatement.allowed_transitions["reconciled"] == set()


def test_bank_statement_relationships():
    assert hasattr(BankStatement, "lines")
    cols = {c.key for c in BankStatementLine.__table__.columns}
    assert "reconciled" in cols
    assert "journal_entry_id" in cols


def test_customer_invoice_state_machine():
    assert "posted" in CustomerInvoice.allowed_transitions["draft"]
    assert "paid" in CustomerInvoice.allowed_transitions["posted"]
    assert "cancelled" in CustomerInvoice.allowed_transitions["posted"]
    assert CustomerInvoice.allowed_transitions["paid"] == set()


def test_customer_invoice_fields():
    cols = {c.key for c in CustomerInvoice.__table__.columns}
    assert "so_id" in cols
    assert "subtotal" in cols
    assert "tax_amount" in cols
    assert "total" in cols
    assert "amount_paid" in cols
    assert "amount_due" in cols


def test_customer_invoice_line_fields():
    cols = {c.key for c in CustomerInvoiceLine.__table__.columns}
    assert "analytic_account_id" in cols
    assert "discount_pct" in cols
    assert "tax_rate" in cols
    assert "tax_amount" in cols


def test_vendor_bill_state_machine():
    assert "posted" in VendorBill.allowed_transitions["draft"]
    assert "paid" in VendorBill.allowed_transitions["posted"]
    assert VendorBill.allowed_transitions["paid"] == set()


def test_vendor_bill_wht_field():
    cols = {c.key for c in VendorBill.__table__.columns}
    assert "wht_amount" in cols
    assert "po_id" in cols


def test_thai_vat_report_unique_constraint():
    constraint_names = {c.name for c in ThaiVatReport.__table__.constraints}
    assert "uq_vat_report_company_period" in constraint_names


def test_thai_vat_report_fields():
    cols = {c.key for c in ThaiVatReport.__table__.columns}
    assert "total_vat_output" in cols
    assert "total_vat_input" in cols
    assert "net_vat" in cols
    assert "rd_ref" in cols


def test_thai_pnd1_report_unique_constraint():
    constraint_names = {c.name for c in ThaiPnd1Report.__table__.constraints}
    assert "uq_pnd1_report_company_period" in constraint_names


def test_closing_entry_unique_constraint():
    constraint_names = {c.name for c in AccountingClosingEntry.__table__.constraints}
    assert "uq_closing_entry_fy_company" in constraint_names


# ── Service pure functions ─────────────────────────────────────────────


def test_compute_invoice_line_standard():
    result = compute_invoice_line(qty=10, unit_price=100.0, discount_pct=0, tax_rate=7.0)
    assert result["subtotal"] == 1000.0
    assert result["tax_amount"] == 70.0
    assert result["total"] == 1070.0


def test_compute_invoice_line_with_discount():
    result = compute_invoice_line(qty=1, unit_price=1000.0, discount_pct=10.0, tax_rate=7.0)
    assert result["subtotal"] == 900.0
    assert result["tax_amount"] == pytest.approx(63.0, rel=0.01)


def test_compute_invoice_line_zero_tax():
    result = compute_invoice_line(qty=5, unit_price=200.0, discount_pct=0, tax_rate=0.0)
    assert result["subtotal"] == 1000.0
    assert result["tax_amount"] == 0.0
    assert result["total"] == 1000.0


def test_compute_invoice_line_fractional_qty():
    result = compute_invoice_line(qty=0.5, unit_price=200.0, discount_pct=0, tax_rate=7.0)
    assert result["subtotal"] == 100.0
    assert result["tax_amount"] == 7.0
