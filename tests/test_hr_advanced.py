"""Tests for advanced HR models and service (Thai SSO/PVD/progressive tax, payroll)."""

import pytest

from backend.modules.hr.models import Employee, Payslip, PayslipLine
from backend.modules.hr.models_advanced import (
    Appraisal,
    AppraisalLine,
    Contract,
    Expense,
    ExpenseLine,
    JobPosition,
    OvertimeRequest,
    ProvidentFund,
    ProvidentFundMember,
    ShiftRoster,
    ThaiPnd1Line,
    ThaiSsoRecord,
    TrainingCourse,
    TrainingEnrollment,
)
from backend.modules.hr.service import (
    SSO_MAX_AMOUNT,
    SSO_MAX_BASE,
    compute_monthly_wht,
    compute_progressive_tax,
    compute_provident_fund,
    compute_thai_sso,
)


# ── Model structure ────────────────────────────────────────────────────


def test_employee_new_fields():
    cols = {c.key for c in Employee.__table__.columns}
    assert "company_id" in cols
    assert "manager_id" in cols
    assert "job_position_id" in cols
    assert "sso_number" in cols
    assert "provident_fund_id" in cols


def test_payslip_thai_fields():
    cols = {c.key for c in Payslip.__table__.columns}
    assert "sso_employee" in cols
    assert "sso_employer" in cols
    assert "provident_fund_employee" in cols
    assert "provident_fund_employer" in cols
    assert "income_tax" in cols
    assert "net_after_tax" in cols


def test_job_position_fields():
    cols = {c.key for c in JobPosition.__table__.columns}
    assert "department_id" in cols
    assert "no_of_recruitment" in cols
    assert "active" in cols


def test_contract_state_machine():
    assert "running" in Contract.allowed_transitions["draft"]
    assert "cancelled" in Contract.allowed_transitions["draft"]
    assert "expired" in Contract.allowed_transitions["running"]
    assert Contract.allowed_transitions["expired"] == set()


def test_contract_fields():
    cols = {c.key for c in Contract.__table__.columns}
    assert "employee_id" in cols
    assert "structure_id" in cols
    assert "contract_type" in cols
    assert "wage" in cols
    assert "date_start" in cols


def test_appraisal_state_machine():
    assert "confirmed" in Appraisal.allowed_transitions["draft"]
    assert "done" in Appraisal.allowed_transitions["confirmed"]
    assert Appraisal.allowed_transitions["done"] == set()


def test_appraisal_relationships():
    assert hasattr(Appraisal, "lines")
    cols = {c.key for c in AppraisalLine.__table__.columns}
    assert "criteria" in cols
    assert "weight" in cols
    assert "score" in cols


def test_expense_state_machine():
    assert "submitted" in Expense.allowed_transitions["draft"]
    assert "approved" in Expense.allowed_transitions["submitted"]
    assert "refused" in Expense.allowed_transitions["submitted"]
    assert "paid" in Expense.allowed_transitions["approved"]
    assert Expense.allowed_transitions["paid"] == set()


def test_expense_relationships():
    assert hasattr(Expense, "lines")
    cols = {c.key for c in ExpenseLine.__table__.columns}
    assert "description" in cols
    assert "amount" in cols


def test_training_enrollment_unique_constraint():
    constraint_names = {c.name for c in TrainingEnrollment.__table__.constraints}
    assert "uq_training_enrollment" in constraint_names


def test_provident_fund_fields():
    cols = {c.key for c in ProvidentFund.__table__.columns}
    assert "fund_code" in cols
    assert "employee_rate_pct" in cols
    assert "employer_rate_pct" in cols
    assert "fund_manager" in cols


def test_pvd_member_unique_constraint():
    constraint_names = {c.name for c in ProvidentFundMember.__table__.constraints}
    assert "uq_pvd_member_period" in constraint_names


def test_thai_sso_unique_constraint():
    constraint_names = {c.name for c in ThaiSsoRecord.__table__.constraints}
    assert "uq_sso_employee_period" in constraint_names


def test_thai_sso_fields():
    cols = {c.key for c in ThaiSsoRecord.__table__.columns}
    assert "gross_income" in cols
    assert "sso_base" in cols
    assert "sso_rate_pct" in cols
    assert "sso_amount" in cols
    assert "employer_amount" in cols


def test_pnd1_line_unique_constraint():
    constraint_names = {c.name for c in ThaiPnd1Line.__table__.constraints}
    assert "uq_pnd1_employee_payslip" in constraint_names


def test_shift_roster_unique_constraint():
    constraint_names = {c.name for c in ShiftRoster.__table__.constraints}
    assert "uq_shift_roster_employee_date" in constraint_names


def test_overtime_request_state_machine():
    assert "approved" in OvertimeRequest.allowed_transitions["draft"]
    assert "rejected" in OvertimeRequest.allowed_transitions["draft"]
    assert OvertimeRequest.allowed_transitions["approved"] == set()


# ── Thai SSO pure function ─────────────────────────────────────────────


def test_thai_sso_normal():
    result = compute_thai_sso(30_000)
    assert result["sso_base"] == SSO_MAX_BASE
    assert result["sso_amount"] == SSO_MAX_AMOUNT
    assert result["employer_amount"] == SSO_MAX_AMOUNT


def test_thai_sso_below_cap():
    result = compute_thai_sso(10_000)
    assert result["sso_base"] == 10_000
    assert result["sso_amount"] == pytest.approx(500.0, rel=0.01)


def test_thai_sso_zero():
    result = compute_thai_sso(0)
    assert result["sso_amount"] == 0.0


def test_thai_sso_exactly_at_cap():
    result = compute_thai_sso(15_000)
    assert result["sso_base"] == 15_000
    assert result["sso_amount"] == SSO_MAX_AMOUNT


# ── Thai Progressive Tax pure function ────────────────────────────────


def test_progressive_tax_zero():
    result = compute_progressive_tax(0)
    assert result["annual_tax"] == 0.0
    assert result["monthly_tax"] == 0.0


def test_progressive_tax_below_exemption():
    # Annual income 200,000 — after 50% deduction (max 100k) + 60k exemption = 40k net → 0% band
    result = compute_progressive_tax(200_000)
    assert result["annual_tax"] == 0.0


def test_progressive_tax_in_5pct_band():
    # Annual 400,000 → deduction 100k (50% max) + 60k = net 240,000 → 0%: 150k=0, 5%: 90k=4,500
    result = compute_progressive_tax(400_000)
    assert result["annual_tax"] == pytest.approx(4_500.0, rel=0.01)


def test_progressive_tax_monthly_is_annual_div_12():
    result = compute_progressive_tax(600_000)
    assert result["monthly_tax"] == pytest.approx(result["annual_tax"] / 12, rel=0.01)


def test_progressive_tax_high_income():
    result = compute_progressive_tax(6_000_000)
    assert result["annual_tax"] > 0
    assert result["monthly_tax"] > 0


# ── Provident Fund pure function ───────────────────────────────────────


def test_pvd_compute_basic():
    result = compute_provident_fund(50_000, employee_rate_pct=5.0, employer_rate_pct=5.0)
    assert result["contribution_employee"] == 2_500.0
    assert result["contribution_employer"] == 2_500.0


def test_pvd_asymmetric_rates():
    result = compute_provident_fund(50_000, employee_rate_pct=3.0, employer_rate_pct=7.0)
    assert result["contribution_employee"] == 1_500.0
    assert result["contribution_employer"] == 3_500.0


def test_pvd_zero_income():
    result = compute_provident_fund(0, 5.0, 5.0)
    assert result["contribution_employee"] == 0.0


# ── Monthly WHT ────────────────────────────────────────────────────────


def test_monthly_wht_consistent_with_annual():
    monthly_gross = 50_000
    monthly_wht = compute_monthly_wht(monthly_gross)
    annual_result = compute_progressive_tax(monthly_gross * 12)
    assert monthly_wht == pytest.approx(annual_result["monthly_tax"], rel=0.01)
