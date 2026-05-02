"""Seed sample payroll batch for May 2026 + ภงด.91 for one employee."""
import datetime
env = self.env  # noqa: F821

# Pick 5 active employees
emps = env["hr.employee"].search([("active", "=", True)], limit=5)
if not emps:
    print("No employees")
else:
    print(f"Using {len(emps)} employees: {emps.mapped('name')}")

# ─── 1. Create May 2026 payroll batch ─────────────────────────────
year, month = 2026, 5
batch = env["kob.payroll.batch"].search([
    ("period_year", "=", year),
    ("period_month", "=", month),
    ("company_id", "=", 1),
], limit=1)
if not batch:
    batch = env["kob.payroll.batch"].create({
        "period_year": year,
        "period_month": month,
        "company_id": 1,
    })
    print(f"  ✓ Created batch {batch.name}")
else:
    print(f"  · Batch {batch.name} exists")

# Generate payslips for the 5 employees with sample salaries
SAMPLE_SALARIES = [25000, 35000, 45000, 60000, 85000]
for emp, salary in zip(emps, SAMPLE_SALARIES):
    existing = env["kob.payslip"].search([
        ("employee_id", "=", emp.id),
        ("period_year", "=", year),
        ("period_month", "=", month),
    ], limit=1)
    if existing:
        continue
    slip = env["kob.payslip"].create({
        "employee_id": emp.id,
        "company_id": 1,
        "batch_id": batch.id,
        "period_year": year,
        "period_month": month,
        "base_salary": salary,
        "bonus": salary * 0.05,  # 5% bonus
        "allowance": 2000,        # transport
    })
    slip.action_calculate()
    slip.action_approve()
    print(f"    ✓ {emp.name}: base={salary:>7,} bonus={int(salary*0.05):>5,} "
          f"gross={int(slip.gross_pay):>7,} sso={int(slip.sso_employee):>4,} "
          f"wht={int(slip.wht_pnd1):>5,} net={int(slip.net_pay):>7,}")

if batch.state == "draft":
    batch.state = "generated"
env.cr.commit()

# ─── 2. Annual cert for first employee ─────────────────────────────
print("\n=== Annual Tax Certificate ภงด.91 ===")
cert = env["kob.tax.cert.annual"].search([
    ("employee_id", "=", emps[0].id),
    ("tax_year", "=", year),
], limit=1)
if not cert:
    cert = env["kob.tax.cert.annual"].create({
        "employee_id": emps[0].id,
        "tax_year": year,
        "company_id": 1,
        "deduction_other": 50000,  # life insurance + RMF estimate
    })
    cert.action_calculate()
    print(f"  ✓ {cert.name}")
    print(f"    Annual gross:   {int(cert.annual_gross):>10,}")
    print(f"    Personal ded:   {int(cert.deduction_personal):>10,}")
    print(f"    SSO ded:        {int(cert.deduction_sso):>10,}")
    print(f"    Other ded:      {int(cert.deduction_other):>10,}")
    print(f"    Taxable:        {int(cert.taxable_income):>10,}")
    print(f"    Tax payable:    {int(cert.tax_payable):>10,}")
    print(f"    Withheld:       {int(cert.tax_withheld):>10,}")
    print(f"    Refund/Due:     {int(cert.refund_or_due):>10,}")

env.cr.commit()

# ─── Summary ──────────────────────────────────────────────────────
print(f"\n=== Batch Summary ===")
print(f"  {batch.name}")
print(f"    Total Gross:  {int(batch.total_gross):>12,}")
print(f"    Total SSO:    {int(batch.total_sso):>12,}")
print(f"    Total WHT:    {int(batch.total_wht):>12,}")
print(f"    Total Net:    {int(batch.total_net):>12,}")
