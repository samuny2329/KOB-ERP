"""Phase 12 group extras — unit tests for models, schemas, services."""

from __future__ import annotations

from datetime import date

import pytest

from backend.modules.group import (
    models_finance,
    models_governance,
    models_partner,
)
from backend.modules.group.service_extra import (
    classify_cash_risk,
    match_rebate_tier,
)


# ── Field shape ────────────────────────────────────────────────────────


def test_xc_customer_uniqueness() -> None:
    constraints = {
        c.name for c in models_partner.CrossCompanyCustomerLink.__table__.constraints if c.name
    }
    assert "uq_xc_customer_link" in constraints
    assert "uq_xc_customer_local" in constraints


def test_xc_vendor_uniqueness() -> None:
    constraints = {
        c.name for c in models_partner.CrossCompanyVendorLink.__table__.constraints if c.name
    }
    assert "uq_xc_vendor_link" in constraints
    assert "uq_xc_vendor_local" in constraints


def test_volume_rebate_tier_uniqueness() -> None:
    constraints = {
        c.name for c in models_partner.VolumeRebateTier.__table__.constraints if c.name
    }
    assert "uq_rebate_tier" in constraints


def test_volume_rebate_accrual_uniqueness() -> None:
    constraints = {
        c.name for c in models_partner.VolumeRebateAccrual.__table__.constraints if c.name
    }
    assert "uq_rebate_accrual" in constraints


def test_bank_account_uniqueness() -> None:
    constraints = {
        c.name for c in models_finance.BankAccount.__table__.constraints if c.name
    }
    assert "uq_bank_account" in constraints


def test_cash_forecast_uniqueness() -> None:
    constraints = {
        c.name for c in models_finance.CashForecastSnapshot.__table__.constraints if c.name
    }
    assert "uq_cash_forecast" in constraints


def test_sku_bridge_uniqueness() -> None:
    constraints = {
        c.name for c in models_governance.SkuBridgeMember.__table__.constraints if c.name
    }
    assert "uq_sku_bridge_company" in constraints
    assert "uq_sku_bridge_local" in constraints


def test_brand_license_uniqueness() -> None:
    constraints = {
        c.name for c in models_governance.BrandLicense.__table__.constraints if c.name
    }
    assert "uq_brand_license_window" in constraints


def test_transfer_pricing_uniqueness() -> None:
    constraints = {
        c.name for c in models_governance.TransferPricingAgreement.__table__.constraints if c.name
    }
    assert "uq_transfer_pricing_window" in constraints


def test_approval_substitution_uniqueness() -> None:
    constraints = {
        c.name for c in models_governance.ApprovalSubstitution.__table__.constraints if c.name
    }
    assert "uq_approval_substitution" in constraints


def test_all_phase12_models_in_grp_schema() -> None:
    """All Phase 12 tables must live in the grp schema."""
    for cls in (
        models_partner.CrossCompanyCustomer,
        models_partner.CrossCompanyCustomerLink,
        models_partner.CrossCompanyVendor,
        models_partner.CrossCompanyVendorLink,
        models_partner.VolumeRebateTier,
        models_partner.VolumeRebateAccrual,
        models_finance.BankAccount,
        models_finance.CashPool,
        models_finance.CashPoolMember,
        models_finance.CashForecastSnapshot,
        models_finance.GroupAccrual,
        models_governance.SkuBridge,
        models_governance.SkuBridgeMember,
        models_governance.BrandLicense,
        models_governance.TransferPricingAgreement,
        models_governance.ApprovalSubstitution,
    ):
        assert cls.__table__.schema == "grp", f"{cls.__name__} schema is {cls.__table__.schema}"


# ── Catalogue tests ────────────────────────────────────────────────────


def test_rebate_periods_catalogue() -> None:
    assert {"monthly", "quarterly", "annual"} == set(models_partner.REBATE_PERIODS)


def test_bank_account_types() -> None:
    expected = {"checking", "savings", "fixed", "credit_line", "petty_cash"}
    assert expected == set(models_finance.BANK_ACCOUNT_TYPES)


def test_license_scopes() -> None:
    assert {"exclusive", "non_exclusive", "co_exclusive"} == set(
        models_governance.LICENSE_SCOPES
    )


def test_pricing_methods_include_thai_compliance_methods() -> None:
    methods = set(models_governance.PRICING_METHODS)
    # TNMM = Transactional Net Margin Method (used in Thai TP documentation)
    assert "tnmm" in methods
    assert "cost_plus" in methods
    assert "resale_minus" in methods


# ── match_rebate_tier ──────────────────────────────────────────────────


def test_match_rebate_tier_picks_top_qualifying() -> None:
    tiers = [
        {"min_spend": 0, "max_spend": 5_000_000, "rebate_pct": 0},
        {"min_spend": 5_000_000, "max_spend": 10_000_000, "rebate_pct": 3},
        {"min_spend": 10_000_000, "max_spend": None, "rebate_pct": 5},
    ]
    matched = match_rebate_tier(tiers, total_spend=12_000_000)
    assert matched is not None
    assert matched["rebate_pct"] == 5


def test_match_rebate_tier_returns_none_when_below_threshold() -> None:
    tiers = [
        {"min_spend": 1_000_000, "max_spend": None, "rebate_pct": 3},
    ]
    matched = match_rebate_tier(tiers, total_spend=500_000)
    assert matched is None


def test_match_rebate_tier_picks_lower_tier() -> None:
    tiers = [
        {"min_spend": 0, "max_spend": 5_000_000, "rebate_pct": 0},
        {"min_spend": 5_000_000, "max_spend": 10_000_000, "rebate_pct": 3},
        {"min_spend": 10_000_000, "max_spend": None, "rebate_pct": 5},
    ]
    matched = match_rebate_tier(tiers, total_spend=7_000_000)
    assert matched["rebate_pct"] == 3


def test_match_rebate_tier_open_max() -> None:
    tiers = [{"min_spend": 0, "max_spend": None, "rebate_pct": 1.5}]
    matched = match_rebate_tier(tiers, total_spend=999_999_999)
    assert matched is not None
    assert matched["rebate_pct"] == 1.5


# ── classify_cash_risk ─────────────────────────────────────────────────


def test_cash_risk_negative_balance_critical() -> None:
    assert classify_cash_risk(projected_balance=-1000, target_balance=100_000) == "critical"


def test_cash_risk_at_target_ok() -> None:
    assert classify_cash_risk(projected_balance=100_000, target_balance=100_000) == "ok"


def test_cash_risk_below_threshold_low() -> None:
    # Target 100k, projected 70k → 30% delta which is >= 20% threshold → low
    assert classify_cash_risk(
        projected_balance=70_000, target_balance=100_000, threshold_pct=20
    ) == "low"


def test_cash_risk_no_target_ok_when_positive() -> None:
    assert classify_cash_risk(projected_balance=50_000, target_balance=0) == "ok"
