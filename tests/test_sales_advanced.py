"""Tests for advanced sales models and service logic."""

import pytest
from datetime import date, datetime, timezone

from backend.modules.sales.models import Customer, SalesOrder, SoLine, SO_STATES
from backend.modules.sales.models_advanced import (
    EtaxInvoiceRef,
    IntercompanySalesOrder,
    PlatformFeeRule,
    QuotationTemplate,
    QuotationTemplateLine,
    RmaLine,
    RmaOrder,
    SalesPricelist,
    SalesPriceRule,
    SalesTeam,
    SoMarginLine,
)
from backend.modules.sales.service import compute_so_margin, _find_best_rule


# ── Model Structure ────────────────────────────────────────────────────


def test_so_states_includes_sent():
    assert "sent" in SO_STATES
    assert "draft" in SO_STATES
    assert "confirmed" in SO_STATES
    assert "cancelled" in SO_STATES


def test_so_state_machine_sent_transition():
    assert "sent" in SalesOrder.allowed_transitions["draft"]
    assert "confirmed" in SalesOrder.allowed_transitions["sent"]
    assert "cancelled" in SalesOrder.allowed_transitions["sent"]
    assert SalesOrder.allowed_transitions["invoiced"] == set()


def test_customer_new_fields():
    cols = {c.key for c in Customer.__table__.columns}
    assert "salesperson_id" in cols
    assert "payment_term_id" in cols
    assert "fiscal_position" in cols
    assert "company_id" in cols
    assert "group_customer_id" in cols


def test_so_new_fields():
    cols = {c.key for c in SalesOrder.__table__.columns}
    assert "sent_at" in cols
    assert "salesperson_id" in cols
    assert "sales_team_id" in cols
    assert "payment_term_id" in cols
    assert "incoterms" in cols
    assert "invoicing_policy" in cols
    assert "pricelist_id" in cols
    assert "company_id" in cols
    assert "ic_po_id" in cols


def test_so_line_tax_and_margin_fields():
    cols = {c.key for c in SoLine.__table__.columns}
    assert "tax_rate" in cols
    assert "tax_amount" in cols
    assert "margin_amount" in cols
    assert "platform_fee_amount" in cols
    assert "true_margin" in cols


def test_sales_team_fields():
    cols = {c.key for c in SalesTeam.__table__.columns}
    assert "code" in cols
    assert "manager_id" in cols
    assert "active" in cols


def test_pricelist_relationships():
    assert hasattr(SalesPricelist, "rules")
    cols = {c.key for c in SalesPriceRule.__table__.columns}
    assert "pricelist_id" in cols
    assert "min_qty" in cols
    assert "date_from" in cols
    assert "date_to" in cols


def test_rma_state_machine():
    assert "confirmed" in RmaOrder.allowed_transitions["draft"]
    assert "cancelled" in RmaOrder.allowed_transitions["draft"]
    assert "received" in RmaOrder.allowed_transitions["confirmed"]
    assert "done" in RmaOrder.allowed_transitions["received"]
    assert RmaOrder.allowed_transitions["done"] == set()


def test_rma_relationships():
    assert hasattr(RmaOrder, "lines")
    cols = {c.key for c in RmaLine.__table__.columns}
    assert "qty_requested" in cols
    assert "qty_received" in cols
    assert "return_reason" in cols


def test_quotation_template_relationships():
    assert hasattr(QuotationTemplate, "lines")
    cols = {c.key for c in QuotationTemplateLine.__table__.columns}
    assert "discount_pct" in cols
    assert "unit_price" in cols


def test_platform_fee_rule_unique_constraint():
    constraint_names = {c.name for c in PlatformFeeRule.__table__.constraints}
    assert "uq_platform_fee_rule" in constraint_names


def test_so_margin_line_fields():
    cols = {c.key for c in SoMarginLine.__table__.columns}
    assert "so_line_id" in cols
    assert "cogs" in cols
    assert "platform_fee" in cols
    assert "gross_margin" in cols
    assert "margin_pct" in cols
    assert "captured_at" in cols


def test_etax_invoice_unique_constraint():
    constraint_names = {c.name for c in EtaxInvoiceRef.__table__.constraints}
    assert "uq_etax_number_company" in constraint_names


def test_intercompany_so_fields():
    cols = {c.key for c in IntercompanySalesOrder.__table__.columns}
    assert "from_company_id" in cols
    assert "to_company_id" in cols
    assert "so_id" in cols
    assert "po_id" in cols
    assert "transfer_price_rule_id" in cols
    assert "status" in cols


# ── Service Logic ──────────────────────────────────────────────────────


def test_compute_so_margin_basic():
    result = compute_so_margin(1000.0, 600.0, "shopee", 3.0)
    assert result["revenue"] == 1000.0
    assert result["cogs"] == 600.0
    assert result["platform_fee"] == 30.0
    assert result["gross_margin"] == 370.0
    assert result["margin_pct"] == pytest.approx(37.0, rel=0.01)


def test_compute_so_margin_zero_revenue():
    result = compute_so_margin(0.0, 0.0, None, 0.0)
    assert result["gross_margin"] == 0.0
    assert result["margin_pct"] == 0.0


def test_compute_so_margin_no_platform_fee():
    result = compute_so_margin(500.0, 300.0, None, 0.0)
    assert result["platform_fee"] == 0.0
    assert result["gross_margin"] == 200.0


def test_find_best_rule_selects_lowest_price():
    today = date.today()
    rules = [
        SalesPriceRule(pricelist_id=1, product_id=1, min_qty=0, price=100),
        SalesPriceRule(pricelist_id=1, product_id=1, min_qty=0, price=90),
        SalesPriceRule(pricelist_id=1, product_id=1, min_qty=0, price=110),
    ]
    best = _find_best_rule(rules, product_id=1, qty=1, today=today)
    assert float(best.price) == 90.0


def test_find_best_rule_filters_by_min_qty():
    today = date.today()
    rules = [
        SalesPriceRule(pricelist_id=1, product_id=1, min_qty=10, price=80),
        SalesPriceRule(pricelist_id=1, product_id=1, min_qty=0, price=100),
    ]
    best = _find_best_rule(rules, product_id=1, qty=5, today=today)
    assert float(best.price) == 100.0


def test_find_best_rule_no_match_returns_none():
    rules = [
        SalesPriceRule(pricelist_id=1, product_id=99, min_qty=0, price=50),
    ]
    best = _find_best_rule(rules, product_id=1, qty=1, today=date.today())
    assert best is None
