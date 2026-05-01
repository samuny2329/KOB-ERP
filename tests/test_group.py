"""Group / multi-company module tests — Phase 11."""

from __future__ import annotations

import pytest

from backend.core.workflow import WorkflowMixin
from backend.modules.group import models, schemas
from backend.modules.group.service import compute_allocation_shares, rank_pool_options


# ── State machines ─────────────────────────────────────────────────────


def test_cost_allocation_state_flow() -> None:
    flow = models.CostAllocation.allowed_transitions
    assert flow["draft"] == {"calculated", "cancelled"}
    assert flow["calculated"] == {"posted", "draft", "cancelled"}
    assert flow["posted"] == set()
    assert flow["cancelled"] == set()


def test_intercompany_loan_state_flow() -> None:
    flow = models.InterCompanyLoan.allowed_transitions
    assert flow["draft"] == {"active", "cancelled"}
    assert flow["active"] == {"settled", "defaulted"}
    assert flow["settled"] == set()
    assert flow["defaulted"] == set()


def test_compliance_item_state_flow_supports_overdue_recovery() -> None:
    flow = models.CompanyComplianceItem.allowed_transitions
    # Overdue can return to in_progress (you can still finish a late filing)
    assert "in_progress" in flow["overdue"]
    assert "submitted" in flow["overdue"]


def test_workflow_mixins() -> None:
    assert issubclass(models.CostAllocation, WorkflowMixin)
    assert issubclass(models.InterCompanyLoan, WorkflowMixin)
    assert issubclass(models.CompanyComplianceItem, WorkflowMixin)


# ── Field shape ────────────────────────────────────────────────────────


def test_kpi_snapshot_uniqueness() -> None:
    constraints = {
        c.name for c in models.GroupKpiSnapshot.__table__.constraints if c.name
    }
    assert "uq_group_kpi_window" in constraints


def test_inventory_pool_member_uniqueness() -> None:
    constraints = {
        c.name for c in models.InventoryPoolMember.__table__.constraints if c.name
    }
    assert "uq_pool_member" in constraints


def test_tax_group_member_uniqueness() -> None:
    constraints = {
        c.name for c in models.TaxGroupMember.__table__.constraints if c.name
    }
    assert "uq_tax_group_member" in constraints


def test_approval_matrix_uniqueness() -> None:
    constraints = {
        c.name for c in models.ApprovalMatrix.__table__.constraints if c.name
    }
    assert "uq_approval_matrix_doc" in constraints


def test_models_in_grp_schema() -> None:
    """Every group model must live in the grp schema (not Postgres reserved 'group')."""
    for cls in (
        models.GroupKpiSnapshot,
        models.InventoryPool,
        models.InventoryPoolMember,
        models.InventoryPoolRule,
        models.CostAllocation,
        models.CostAllocationLine,
        models.InterCompanyLoan,
        models.LoanInstallment,
        models.TaxGroup,
        models.TaxGroupMember,
        models.ApprovalMatrix,
        models.ApprovalMatrixRule,
        models.CompanyComplianceItem,
    ):
        assert cls.__table__.schema == "grp", f"{cls.__name__} schema = {cls.__table__.schema}"


# ── Catalogues ─────────────────────────────────────────────────────────


def test_kpi_metrics_catalogue() -> None:
    expected = {
        "revenue", "gross_margin", "fulfillment_sla_pct", "pick_accuracy_pct",
        "ar_days", "ap_days", "headcount", "active_customers",
    }
    assert expected == set(models.KPI_METRICS)


def test_routing_strategies_catalogue() -> None:
    assert {"priority", "lowest_cost", "nearest", "balance_load"} == set(
        models.ROUTING_STRATEGIES
    )


def test_compliance_types_thai_specific() -> None:
    """Thai SME compliance types must include PND/SSO."""
    types = set(models.COMPLIANCE_TYPES)
    for required in ("vat_pp30", "wht_pnd1", "wht_pnd3", "wht_pnd53", "social_security"):
        assert required in types


def test_approvable_docs_catalogue() -> None:
    assert "purchase_order" in models.APPROVABLE_DOCS
    assert "intercompany_loan" in models.APPROVABLE_DOCS
    assert "cost_allocation" in models.APPROVABLE_DOCS


def test_allocation_basis_catalogue() -> None:
    expected = {"revenue_pct", "headcount_pct", "fixed", "sqm_pct", "manual"}
    assert expected == set(models.ALLOCATION_BASIS)


# ── compute_allocation_shares ──────────────────────────────────────────


def test_allocation_revenue_pct_basis() -> None:
    members = [
        {"company_id": 1, "revenue": 1_000_000},
        {"company_id": 2, "revenue": 3_000_000},
    ]
    out = compute_allocation_shares(total=10_000, members=members, basis="revenue_pct")
    assert len(out) == 2
    assert out[0]["share_pct"] == 25.0
    assert out[1]["share_pct"] == 75.0
    assert out[0]["amount"] == 2_500.0
    assert out[1]["amount"] == 7_500.0


def test_allocation_headcount_pct() -> None:
    members = [
        {"company_id": 1, "headcount": 30},
        {"company_id": 2, "headcount": 70},
    ]
    out = compute_allocation_shares(total=100_000, members=members, basis="headcount_pct")
    assert out[0]["amount"] == 30_000.0
    assert out[1]["amount"] == 70_000.0


def test_allocation_fixed_basis() -> None:
    members = [
        {"company_id": 1, "manual_amount": 4_000},
        {"company_id": 2, "manual_amount": 6_000},
    ]
    out = compute_allocation_shares(total=10_000, members=members, basis="fixed")
    assert out[0]["amount"] == 4_000.0
    assert out[1]["amount"] == 6_000.0


def test_allocation_manual_pct() -> None:
    members = [
        {"company_id": 1, "manual_share_pct": 33.33},
        {"company_id": 2, "manual_share_pct": 66.67},
    ]
    out = compute_allocation_shares(total=10_000, members=members, basis="manual")
    assert abs(out[0]["amount"] - 3_333.0) < 1
    assert abs(out[1]["amount"] - 6_667.0) < 1


def test_allocation_zero_weight_raises() -> None:
    members = [{"company_id": 1, "revenue": 0}]
    with pytest.raises(ValueError, match="must be > 0"):
        compute_allocation_shares(total=1000, members=members, basis="revenue_pct")


def test_allocation_unknown_basis_raises() -> None:
    with pytest.raises(ValueError, match="unknown basis"):
        compute_allocation_shares(total=1000, members=[], basis="invalid_basis")


# ── rank_pool_options ──────────────────────────────────────────────────


def test_rank_pool_priority_strategy() -> None:
    members = [
        {"company_id": 1, "warehouse_id": 1, "available_qty": 100, "priority": 50, "transfer_cost_per_km": 1},
        {"company_id": 2, "warehouse_id": 2, "available_qty": 100, "priority": 10, "transfer_cost_per_km": 5},
    ]
    out = rank_pool_options(members, qty_required=50, strategy="priority")
    assert out[0]["warehouse_id"] == 2  # priority 10 wins
    assert out[0]["chosen"] is True
    assert out[1]["chosen"] is False


def test_rank_pool_lowest_cost_strategy() -> None:
    members = [
        {"company_id": 1, "warehouse_id": 1, "available_qty": 100, "priority": 10, "transfer_cost_per_km": 5},
        {"company_id": 2, "warehouse_id": 2, "available_qty": 100, "priority": 20, "transfer_cost_per_km": 1},
    ]
    out = rank_pool_options(members, qty_required=10, strategy="lowest_cost")
    assert out[0]["warehouse_id"] == 2  # cheaper
    assert out[0]["estimated_cost"] == 10.0


def test_rank_pool_balance_load_picks_most_stocked() -> None:
    members = [
        {"company_id": 1, "warehouse_id": 1, "available_qty": 50, "priority": 10},
        {"company_id": 2, "warehouse_id": 2, "available_qty": 200, "priority": 20},
    ]
    out = rank_pool_options(members, qty_required=10, strategy="balance_load")
    assert out[0]["warehouse_id"] == 2  # most stocked


def test_rank_pool_short_members_pushed_back() -> None:
    members = [
        {"company_id": 1, "warehouse_id": 1, "available_qty": 5, "priority": 1},   # short
        {"company_id": 2, "warehouse_id": 2, "available_qty": 100, "priority": 50}, # plenty
    ]
    out = rank_pool_options(members, qty_required=50, strategy="priority")
    # In-stock member chosen even if higher priority number
    assert out[0]["warehouse_id"] == 2
    assert out[1]["short"] is True


# ── Schema literals ────────────────────────────────────────────────────


def test_schemas_consistent() -> None:
    """Make sure 'grp' is in SCHEMAS list (Postgres-reserved word workaround)."""
    from backend.core.db import SCHEMAS

    assert "grp" in SCHEMAS
    assert "group" not in SCHEMAS  # 'group' is reserved in Postgres
