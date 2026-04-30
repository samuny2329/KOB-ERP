"""Tests for advanced purchase models — Odoo 19 parity + KOB-exclusive features."""

import pytest
from datetime import date, timedelta

from backend.modules.purchase.models import PurchaseOrder, PoLine, PO_STATES, PO_APPROVAL_STATES, INCOTERMS
from backend.modules.purchase.models_advanced import (
    DemandSignal,
    PaymentTerm,
    PaymentTermLine,
    PoConsolidationProposal,
    ProcurementBudget,
    SupplierPricelist,
    VendorDocument,
    VendorPerformance,
    WhtCertificate,
    VENDOR_DOC_TYPES,
    WHT_TYPES,
)
from backend.modules.purchase.schemas_advanced import (
    PaymentTermCreate,
    ProcurementBudgetCreate,
    SupplierPricelistCreate,
    WhtCertificateCreate,
)


# ── PO model structure tests ───────────────────────────────────────────


def test_po_states_includes_waiting_approval():
    assert "waiting_approval" in PO_STATES
    assert "confirmed" in PO_STATES
    assert "cancelled" in PO_STATES


def test_po_approval_states():
    assert "pending" in PO_APPROVAL_STATES
    assert "approved" in PO_APPROVAL_STATES
    assert "rejected" in PO_APPROVAL_STATES
    assert "not_required" in PO_APPROVAL_STATES


def test_po_state_machine_transitions():
    assert "waiting_approval" in PurchaseOrder.allowed_transitions["draft"]
    assert "confirmed" in PurchaseOrder.allowed_transitions["waiting_approval"]
    assert "cancelled" in PurchaseOrder.allowed_transitions["waiting_approval"]
    assert PurchaseOrder.allowed_transitions["closed"] == set()


def test_incoterms_includes_common_codes():
    assert "FOB" in INCOTERMS
    assert "CIF" in INCOTERMS
    assert "DDP" in INCOTERMS
    assert "EXW" in INCOTERMS


def test_po_has_buyer_and_incoterms_fields():
    cols = {c.key for c in PurchaseOrder.__table__.columns}
    assert "buyer_id" in cols
    assert "incoterms" in cols
    assert "note_internal" in cols
    assert "note_vendor" in cols
    assert "approval_state" in cols
    assert "budget_id" in cols
    assert "payment_term_id" in cols


def test_po_line_has_tax_fields():
    cols = {c.key for c in PoLine.__table__.columns}
    assert "tax_id" in cols
    assert "tax_rate" in cols
    assert "tax_amount" in cols
    assert "total" in cols


# ── Advanced model structure tests ────────────────────────────────────


def test_payment_term_model_fields():
    cols = {c.key for c in PaymentTerm.__table__.columns}
    assert "name" in cols
    assert "active" in cols
    assert hasattr(PaymentTerm, "lines")


def test_payment_term_line_fields():
    cols = {c.key for c in PaymentTermLine.__table__.columns}
    assert "value_type" in cols
    assert "days" in cols
    assert "discount_pct" in cols
    assert "discount_days" in cols


def test_supplier_pricelist_fields():
    cols = {c.key for c in SupplierPricelist.__table__.columns}
    assert "vendor_id" in cols
    assert "product_id" in cols
    assert "min_qty" in cols
    assert "price" in cols
    assert "lead_time_days" in cols
    assert "effective_from" in cols
    assert "effective_to" in cols


def test_vendor_document_types():
    assert "iso_cert" in VENDOR_DOC_TYPES
    assert "insurance" in VENDOR_DOC_TYPES
    assert "contract" in VENDOR_DOC_TYPES
    cols = {c.key for c in VendorDocument.__table__.columns}
    assert "expiry_date" in cols
    assert "alert_days_before" in cols
    assert "file_url" in cols


def test_vendor_performance_fields():
    cols = {c.key for c in VendorPerformance.__table__.columns}
    assert "on_time_rate" in cols
    assert "fill_rate" in cols
    assert "quality_rate" in cols
    assert "price_stability" in cols
    assert "overall_score" in cols


def test_vendor_performance_unique_constraint():
    constraint_names = {c.name for c in VendorPerformance.__table__.constraints}
    assert "uq_vendor_perf_period" in constraint_names


def test_wht_certificate_types():
    assert "pnd3" in WHT_TYPES
    assert "pnd53" in WHT_TYPES
    cols = {c.key for c in WhtCertificate.__table__.columns}
    assert "wht_rate" in cols
    assert "base_amount" in cols
    assert "wht_amount" in cols
    assert "submitted" in cols
    assert "period_month" in cols
    assert "period_year" in cols


def test_procurement_budget_state_machine():
    assert ProcurementBudget.allowed_transitions["draft"] == {"active", "cancelled"}
    assert ProcurementBudget.allowed_transitions["active"] == {"closed", "cancelled"}
    assert ProcurementBudget.allowed_transitions["closed"] == set()


def test_procurement_budget_fields():
    cols = {c.key for c in ProcurementBudget.__table__.columns}
    assert "total_budget" in cols
    assert "committed_amount" in cols
    assert "spent_amount" in cols
    assert "auto_block_overrun" in cols
    assert "project_code" in cols


def test_demand_signal_fields():
    cols = {c.key for c in DemandSignal.__table__.columns}
    assert "avg_daily_sales" in cols
    assert "suggested_qty" in cols
    assert "safety_stock" in cols
    assert "status" in cols
    assert "converted_po_id" in cols


def test_consolidation_proposal_relationships():
    assert hasattr(PoConsolidationProposal, "items")
    cols = {c.key for c in PoConsolidationProposal.__table__.columns}
    assert "estimated_saving" in cols
    assert "saving_pct" in cols
    assert "window_days" in cols


# ── Schema validation tests ────────────────────────────────────────────


def test_payment_term_schema():
    from backend.modules.purchase.schemas_advanced import PaymentTermLineCreate
    pt = PaymentTermCreate(
        name="Net 30",
        lines=[PaymentTermLineCreate(value_type="balance", value=100, days=30)],
    )
    assert pt.active is True
    assert len(pt.lines) == 1


def test_supplier_pricelist_schema_requires_positive_price():
    with pytest.raises(Exception):
        SupplierPricelistCreate(vendor_id=1, product_id=1, price=-5.0)


def test_wht_certificate_schema_period_bounds():
    with pytest.raises(Exception):
        WhtCertificateCreate(
            purchase_order_id=1,
            vendor_id=1,
            wht_type="pnd53",
            wht_rate=3.0,
            base_amount=10000,
            wht_amount=300,
            payment_date=date.today(),
            period_month=13,  # invalid
            period_year=2026,
        )


def test_procurement_budget_schema():
    budget = ProcurementBudgetCreate(
        name="Q1 2026 Budget",
        fiscal_year=2026,
        period_from=date(2026, 1, 1),
        period_to=date(2026, 3, 31),
        total_budget=500000.0,
    )
    assert budget.currency == "THB"
    assert budget.auto_block_overrun is True


def test_vendor_fields_updated():
    from backend.modules.purchase.models import Vendor
    cols = {c.key for c in Vendor.__table__.columns}
    assert "lead_time_days" in cols
    assert "wht_type" in cols
    assert "wht_rate" in cols
    assert "performance_score" in cols
    assert "payment_term_id" in cols
