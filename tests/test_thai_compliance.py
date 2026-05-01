"""Phase 14 Thai compliance — pure-function tests for HR + Accounting."""

from __future__ import annotations

from datetime import date

from backend.modules.accounting.service_advanced import (
    compute_fx_revaluation,
    compute_monthly_depreciation,
)
from backend.modules.hr.models_advanced import OT_MULTIPLIERS
from backend.modules.hr.service_advanced import (
    compute_monthly_wht,
    compute_overtime,
    compute_progressive_tax,
    compute_sso_amounts,
    resolve_leave_grant,
    years_of_service,
)


# ── SSO ────────────────────────────────────────────────────────────────


def test_sso_below_cap() -> None:
    emp, er = compute_sso_amounts(10_000)
    assert emp == 500
    assert er == 500


def test_sso_at_cap() -> None:
    emp, er = compute_sso_amounts(15_000)
    assert emp == 750
    assert er == 750


def test_sso_above_cap_capped() -> None:
    emp, er = compute_sso_amounts(50_000)
    assert emp == 750  # capped
    assert er == 750


# ── PND progressive tax ────────────────────────────────────────────────


def test_pnd_zero_below_threshold() -> None:
    """Annual ≤ 150k = 0% tax."""
    assert compute_progressive_tax(100_000) == 0


def test_pnd_first_bracket() -> None:
    """Annual 200k → tax on 50k @ 5% = 2,500."""
    assert compute_progressive_tax(200_000) == 2_500


def test_pnd_multi_bracket() -> None:
    """Annual 1M = 0 + (300-150)*5% + (500-300)*10% + (750-500)*15% + (1000-750)*20%
       = 0 + 7,500 + 20,000 + 37,500 + 50,000 = 115,000."""
    assert compute_progressive_tax(1_000_000) == 115_000


def test_monthly_wht_round_trip() -> None:
    monthly_taxable = 50_000  # 600k annual
    monthly, rate = compute_monthly_wht(monthly_taxable)
    # 600k → 0 + 7500 + 20000 + (600-500)*15% = 42500/year → 3,541.67/month
    assert 3_500 < monthly < 3_600
    assert 0 < rate < 15


# ── Overtime ───────────────────────────────────────────────────────────


def test_ot_weekday_after_hours() -> None:
    total, mult = compute_overtime("weekday_after_hours", 4, 100)
    assert mult == 1.5
    assert total == 600  # 4 × 100 × 1.5


def test_ot_holiday_3x() -> None:
    total, mult = compute_overtime("holiday", 8, 100)
    assert mult == 3.0
    assert total == 2_400


def test_ot_kinds_complete() -> None:
    expected = {
        "weekday_after_hours",
        "weekend_normal",
        "weekend_after_hours",
        "holiday",
    }
    assert expected == set(OT_MULTIPLIERS.keys())


# ── Leave entitlement ──────────────────────────────────────────────────


def test_leave_first_year_kob_policy() -> None:
    days, rule = resolve_leave_grant(0)
    assert days == 6.0
    assert rule == "kob_policy_first_year"


def test_leave_lpa_minimum() -> None:
    days, rule = resolve_leave_grant(2)
    assert days == 6.0
    assert "lpa_minimum" in rule


def test_leave_long_tenure() -> None:
    days, rule = resolve_leave_grant(15)
    assert days == 14.0
    assert "10_plus" in rule


def test_years_of_service_basic() -> None:
    assert years_of_service(date(2020, 1, 1), date(2024, 1, 1)) == 4
    assert years_of_service(date(2020, 6, 15), date(2024, 6, 14)) == 3
    assert years_of_service(date(2020, 6, 15), date(2024, 6, 15)) == 4


# ── Depreciation ──────────────────────────────────────────────────────


def test_straight_line_depreciation() -> None:
    """100k cost, 10k salvage, 60 months = 1,500/month."""
    amt = compute_monthly_depreciation("straight_line", 100_000, 10_000, 60)
    assert amt == 1_500


def test_declining_balance_first_month() -> None:
    """100k cost, 60 months → first month = 200% × cost / months = 3,333.33."""
    amt = compute_monthly_depreciation("declining_balance", 100_000, 0, 60)
    assert 3_300 < amt < 3_350


# ── FX revaluation ────────────────────────────────────────────────────


def test_fx_revaluation_gain() -> None:
    """USD 1000 booked at 35 (=35,000 THB) revalued at 36 = 36,000 → +1,000 gain."""
    revalued, gl = compute_fx_revaluation(
        booked_balance_fc=1000, booked_balance_thb=35_000, period_end_rate=36
    )
    assert revalued == 36_000
    assert gl == 1_000


def test_fx_revaluation_loss() -> None:
    revalued, gl = compute_fx_revaluation(
        booked_balance_fc=1000, booked_balance_thb=36_000, period_end_rate=35
    )
    assert revalued == 35_000
    assert gl == -1_000
