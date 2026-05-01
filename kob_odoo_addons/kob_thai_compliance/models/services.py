# -*- coding: utf-8 -*-
"""Pure Thai-compliance maths.

Carried over verbatim from the standalone KOB ERP Phase 14 (
``backend/modules/hr/service_advanced.py``).  Every function here is
side-effect-free and Odoo-independent — the same unit tests can be run
against this file directly.
"""

from __future__ import annotations

from datetime import date

# ── SSO ─────────────────────────────────────────────────────────────────

SSO_RATE_PCT = 5.0        # employee 5%, employer 5%
SSO_WAGE_CAP = 15_000.0   # THB monthly wage cap
SSO_MAX_AMOUNT = 750.0    # 5% × 15,000


def compute_sso_amounts(gross_wage):
    """Return ``(employee_amount, employer_amount)`` for one month.

    Both are capped at 750 THB; computed on min(gross_wage, 15000) × 5%.
    """
    capped = min(float(gross_wage), SSO_WAGE_CAP)
    amt = round(capped * SSO_RATE_PCT / 100, 2)
    return amt, amt


# ── PND progressive WHT (simplified Thai brackets, 2024) ────────────────

PND_BRACKETS = [
    (150_000, 0.00),
    (300_000, 0.05),
    (500_000, 0.10),
    (750_000, 0.15),
    (1_000_000, 0.20),
    (2_000_000, 0.25),
    (5_000_000, 0.30),
    (float("inf"), 0.35),
]


def compute_progressive_tax(annual_taxable_income):
    """Sum of marginal tax across PND_BRACKETS."""
    remaining = float(annual_taxable_income)
    last_threshold = 0.0
    tax = 0.0
    for threshold, rate in PND_BRACKETS:
        slice_amount = min(remaining, threshold - last_threshold)
        if slice_amount <= 0:
            break
        tax += slice_amount * rate
        remaining -= slice_amount
        last_threshold = threshold
    return round(tax, 2)


def compute_monthly_wht(monthly_taxable_income):
    """Return ``(monthly_wht, effective_rate_pct)``."""
    annual = float(monthly_taxable_income) * 12
    annual_tax = compute_progressive_tax(annual)
    monthly = round(annual_tax / 12, 2)
    rate_pct = (annual_tax / annual * 100) if annual > 0 else 0
    return monthly, round(rate_pct, 4)


# ── Overtime (Thai LPA multipliers) ─────────────────────────────────────

OT_MULTIPLIERS = {
    "weekday_after_hours": 1.5,
    "weekend_normal": 1.0,
    "weekend_after_hours": 3.0,
    "holiday": 3.0,
}


def compute_overtime(ot_kind, hours, base_hourly_rate):
    """Pure function — returns ``(total_amount, rate_multiplier)``.

    Raises ``KeyError`` for unknown ``ot_kind``; callers translate that
    into an Odoo UserError.
    """
    multiplier = OT_MULTIPLIERS[ot_kind]
    total = round(float(hours) * float(base_hourly_rate) * multiplier, 2)
    return total, multiplier


# ── Leave entitlement (KOB tier above LPA minimum) ──────────────────────


def resolve_leave_grant(years_of_service):
    """Return ``(granted_days, rule_label)``."""
    if years_of_service < 1:
        return 6.0, "kob_policy_first_year"
    if years_of_service < 3:
        return 6.0, "lpa_minimum_1_to_3"
    if years_of_service < 5:
        return 8.0, "kob_tier_3_to_5"
    if years_of_service < 10:
        return 10.0, "kob_tier_5_to_10"
    return 14.0, "kob_tier_10_plus"


def years_of_service(hire_date, asof):
    """Whole-year tenure between two dates."""
    delta = (asof.year - hire_date.year) - (
        1 if (asof.month, asof.day) < (hire_date.month, hire_date.day) else 0
    )
    return max(0, delta)


# ── Depreciation ────────────────────────────────────────────────────────


def compute_monthly_depreciation(method, cost, salvage, useful_months):
    """Straight-line or declining-balance — first-month amount."""
    cost = float(cost)
    salvage = float(salvage)
    useful_months = int(useful_months)
    if useful_months <= 0:
        return 0.0
    if method == "straight_line":
        return round((cost - salvage) / useful_months, 2)
    if method == "declining_balance":
        # 200% declining balance, first month
        return round(cost * 2 / useful_months, 2)
    raise ValueError(f"unknown depreciation method: {method!r}")


# ── FX revaluation ──────────────────────────────────────────────────────


def compute_fx_revaluation(booked_balance_fc, booked_balance_thb, period_end_rate):
    """Return ``(revalued_thb, gain_loss)``.

    Positive gain_loss = unrealised gain.
    """
    revalued = round(float(booked_balance_fc) * float(period_end_rate), 2)
    gl = round(revalued - float(booked_balance_thb), 2)
    return revalued, gl


__all__ = [
    "SSO_RATE_PCT",
    "SSO_WAGE_CAP",
    "SSO_MAX_AMOUNT",
    "compute_sso_amounts",
    "PND_BRACKETS",
    "compute_progressive_tax",
    "compute_monthly_wht",
    "OT_MULTIPLIERS",
    "compute_overtime",
    "resolve_leave_grant",
    "years_of_service",
    "compute_monthly_depreciation",
    "compute_fx_revaluation",
]
