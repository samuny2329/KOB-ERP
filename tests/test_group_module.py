"""Tests for the group module — models and service pure functions."""

import pytest
from datetime import date, datetime, timezone

from backend.core.models import Company
from backend.modules.group.models import (
    CompanyGroup,
    CompanyMembership,
    GroupKpiConfig,
    GroupKpiRollup,
    InventoryPool,
    InventoryPoolMember,
)
from backend.modules.group.models_finance import (
    BankAccount,
    CashForecastSnapshot,
    CashPool,
    CashPoolMember,
    CostAllocationLine,
    CrossCompanyCostAllocation,
    GroupAccrual,
    IntercompanyLoan,
    IntercompanyLoanInstallment,
    TransferPriceRule,
)
from backend.modules.group.models_governance import (
    ApprovalSubstitution,
    BrandLicense,
    CompanyApprovalMatrix,
    ComplianceCalendar,
    ThaiTaxGroup,
)
from backend.modules.group.models_partner import (
    CrossCompanySkuBridge,
    GroupCustomerLink,
    GroupCustomerProfile,
    GroupVendorLink,
    GroupVendorProfile,
    SkuBridgeItem,
    VolumeRebateAccrual,
    VolumeRebateTier,
)
from backend.modules.group.service import (
    classify_cash_risk,
    compute_allocation_shares,
    compute_group_kpi,
    match_rebate_tier,
    rank_pool_options,
)


# ── Company model ──────────────────────────────────────────────────────


def test_company_in_grp_schema():
    assert Company.__table_args__[-1]["schema"] == "grp"
    assert Company.__tablename__ == "company"


def test_company_fields():
    cols = {c.key for c in Company.__table__.columns}
    assert "code" in cols
    assert "name" in cols
    assert "tax_id" in cols
    assert "country" in cols
    assert "currency" in cols
    assert "parent_id" in cols
    assert "active" in cols


# ── Foundation models ──────────────────────────────────────────────────


def test_company_group_membership_relationship():
    assert hasattr(CompanyGroup, "memberships")
    cols = {c.key for c in CompanyMembership.__table__.columns}
    assert "ownership_pct" in cols
    assert "role" in cols
    assert "effective_from" in cols


def test_membership_unique_constraint():
    constraint_names = {c.name for c in CompanyMembership.__table__.constraints}
    assert "uq_company_membership" in constraint_names


def test_kpi_rollup_unique_constraint():
    constraint_names = {c.name for c in GroupKpiRollup.__table__.constraints}
    assert "uq_kpi_company_period_metric" in constraint_names


def test_kpi_config_fields():
    cols = {c.key for c in GroupKpiConfig.__table__.columns}
    assert "metric_name" in cols
    assert "weight" in cols
    assert "aggregation" in cols
    assert "enabled" in cols


def test_inventory_pool_relationships():
    assert hasattr(InventoryPool, "members")
    cols = {c.key for c in InventoryPoolMember.__table__.columns}
    assert "priority" in cols
    assert "warehouse_id" in cols


# ── Partner models ─────────────────────────────────────────────────────


def test_group_customer_profile_fields():
    cols = {c.key for c in GroupCustomerProfile.__table__.columns}
    assert "group_credit_limit" in cols
    assert "group_ltv_score" in cols
    assert "blocked" in cols
    assert "blocked_reason" in cols


def test_group_customer_link_unique_constraint():
    constraint_names = {c.name for c in GroupCustomerLink.__table__.constraints}
    assert "uq_group_customer_link" in constraint_names


def test_group_vendor_profile_fields():
    cols = {c.key for c in GroupVendorProfile.__table__.columns}
    assert "lifetime_spend" in cols
    assert "ytd_spend" in cols
    assert "group_otd_pct" in cols
    assert "group_quality_pct" in cols
    assert "group_score" in cols


def test_volume_rebate_tier_fields():
    cols = {c.key for c in VolumeRebateTier.__table__.columns}
    assert "min_spend" in cols
    assert "rebate_pct" in cols
    assert "period_type" in cols


def test_rebate_accrual_unique_constraint():
    constraint_names = {c.name for c in VolumeRebateAccrual.__table__.constraints}
    assert "uq_rebate_accrual_vendor_period" in constraint_names


def test_sku_bridge_relationships():
    assert hasattr(CrossCompanySkuBridge, "items")
    cols = {c.key for c in SkuBridgeItem.__table__.columns}
    assert "local_sku" in cols
    assert "product_id" in cols
    assert "company_id" in cols


# ── Finance models ─────────────────────────────────────────────────────


def test_cash_pool_member_unique_constraint():
    constraint_names = {c.name for c in CashPoolMember.__table__.constraints}
    assert "uq_cash_pool_member" in constraint_names


def test_cash_forecast_unique_constraint():
    constraint_names = {c.name for c in CashForecastSnapshot.__table__.constraints}
    assert "uq_cash_forecast_company_date" in constraint_names


def test_ic_loan_fields():
    cols = {c.key for c in IntercompanyLoan.__table__.columns}
    assert "lender_id" in cols
    assert "borrower_id" in cols
    assert "principal" in cols
    assert "interest_rate" in cols
    assert "outstanding" in cols


def test_ic_loan_installment_fields():
    cols = {c.key for c in IntercompanyLoanInstallment.__table__.columns}
    assert "principal_amount" in cols
    assert "interest_amount" in cols
    assert "paid" in cols


def test_transfer_price_rule_fields():
    cols = {c.key for c in TransferPriceRule.__table__.columns}
    assert "from_company_id" in cols
    assert "to_company_id" in cols
    assert "method" in cols
    assert "markup_pct" in cols
    assert "documentation_url" in cols


def test_cost_allocation_state_machine():
    assert "validated" in CrossCompanyCostAllocation.allowed_transitions["draft"]
    assert "cancelled" in CrossCompanyCostAllocation.allowed_transitions["draft"]
    assert CrossCompanyCostAllocation.allowed_transitions["validated"] == set()


def test_cost_allocation_relationships():
    assert hasattr(CrossCompanyCostAllocation, "lines")
    cols = {c.key for c in CostAllocationLine.__table__.columns}
    assert "share_pct" in cols
    assert "basis_value" in cols


# ── Governance models ──────────────────────────────────────────────────


def test_compliance_calendar_state_machine():
    assert "submitted" in ComplianceCalendar.allowed_transitions["pending"]
    assert "overdue" in ComplianceCalendar.allowed_transitions["pending"]
    assert "accepted" in ComplianceCalendar.allowed_transitions["submitted"]
    assert "recovered" in ComplianceCalendar.allowed_transitions["overdue"]
    assert ComplianceCalendar.allowed_transitions["accepted"] == set()


def test_compliance_calendar_unique_constraint():
    constraint_names = {c.name for c in ComplianceCalendar.__table__.constraints}
    assert "uq_compliance_filing" in constraint_names


def test_approval_matrix_fields():
    cols = {c.key for c in CompanyApprovalMatrix.__table__.columns}
    assert "document_type" in cols
    assert "amount_threshold" in cols
    assert "approver_id" in cols
    assert "min_approvers" in cols


def test_brand_license_fields():
    cols = {c.key for c in BrandLicense.__table__.columns}
    assert "royalty_pct" in cols
    assert "license_scope" in cols
    assert "valid_from" in cols
    assert "valid_to" in cols


# ── Service pure functions ─────────────────────────────────────────────


def test_compute_allocation_shares_even():
    lines = [{"company_id": 1, "basis_value": 50.0}, {"company_id": 2, "basis_value": 50.0}]
    shares = compute_allocation_shares(lines, "revenue")
    assert shares[1] == pytest.approx(50.0)
    assert shares[2] == pytest.approx(50.0)


def test_compute_allocation_shares_uneven():
    lines = [
        {"company_id": 1, "basis_value": 75.0},
        {"company_id": 2, "basis_value": 25.0},
    ]
    shares = compute_allocation_shares(lines, "revenue")
    assert shares[1] == pytest.approx(75.0)
    assert shares[2] == pytest.approx(25.0)


def test_compute_allocation_shares_zero_basis_equal_split():
    lines = [{"company_id": 1, "basis_value": 0.0}, {"company_id": 2, "basis_value": 0.0}]
    shares = compute_allocation_shares(lines, "equal")
    assert shares[1] == pytest.approx(50.0)
    assert shares[2] == pytest.approx(50.0)


def test_rank_pool_options_priority():
    members = [
        {"company_id": 1, "priority": 10, "available_qty": 100, "unit_cost": 5, "distance_km": 50},
        {"company_id": 2, "priority": 5, "available_qty": 80, "unit_cost": 4, "distance_km": 100},
        {"company_id": 3, "priority": 1, "available_qty": 60, "unit_cost": 6, "distance_km": 10},
    ]
    ranked = rank_pool_options(members, demand_qty=50, strategy="priority")
    assert ranked[0]["company_id"] == 3  # lowest priority number = first
    assert ranked[0]["rank"] == 1


def test_rank_pool_options_lowest_cost():
    members = [
        {"company_id": 1, "priority": 10, "available_qty": 100, "unit_cost": 5.0, "distance_km": 50},
        {"company_id": 2, "priority": 5, "available_qty": 80, "unit_cost": 3.5, "distance_km": 100},
    ]
    ranked = rank_pool_options(members, demand_qty=50, strategy="lowest_cost")
    assert ranked[0]["company_id"] == 2


def test_match_rebate_tier_picks_highest_qualifying():
    tiers = [
        {"min_spend": 0, "rebate_pct": 1.0, "tier_label": "bronze"},
        {"min_spend": 50000, "rebate_pct": 2.0, "tier_label": "silver"},
        {"min_spend": 100000, "rebate_pct": 3.0, "tier_label": "gold"},
    ]
    matched = match_rebate_tier(tiers, ytd_spend=75000)
    assert matched["tier_label"] == "silver"


def test_match_rebate_tier_no_qualifying_returns_none():
    tiers = [{"min_spend": 100000, "rebate_pct": 2.0, "tier_label": "silver"}]
    assert match_rebate_tier(tiers, ytd_spend=5000) is None


def test_classify_cash_risk_ok():
    assert classify_cash_risk(1000, 1000) == "ok"
    assert classify_cash_risk(600, 1000) == "ok"


def test_classify_cash_risk_low():
    assert classify_cash_risk(300, 1000) == "low"


def test_classify_cash_risk_critical():
    assert classify_cash_risk(100, 1000) == "critical"


def test_classify_cash_risk_zero_target():
    assert classify_cash_risk(0, 0) == "ok"


def test_compute_group_kpi_sum():
    tree = [{"company_id": 1, "ownership_pct": 100}, {"company_id": 2, "ownership_pct": 51}]
    values = {1: 1000.0, 2: 500.0}
    assert compute_group_kpi(tree, values, "sum") == 1500.0


def test_compute_group_kpi_avg():
    tree = [{"company_id": 1, "ownership_pct": 100}, {"company_id": 2, "ownership_pct": 51}]
    values = {1: 100.0, 2: 200.0}
    assert compute_group_kpi(tree, values, "avg") == pytest.approx(150.0)


def test_compute_group_kpi_last():
    tree = [{"company_id": 1, "ownership_pct": 100}, {"company_id": 2, "ownership_pct": 51}]
    values = {1: 100.0, 2: 200.0}
    assert compute_group_kpi(tree, values, "last") == 200.0


def test_compute_group_kpi_empty_tree():
    assert compute_group_kpi([], {}, "sum") == 0.0
