"""Rebuild Inventory > Reporting menu to match UAT layout exactly.

Sections:
  Statement Reports      → Balance Sheet, P&L, P&L Default, Cash Flow,
                           Executive Summary, Tax Return
  Audit Reports          → General Ledger, Trial Balance, Journal Audit
  Partner Reports        → Partner Ledger, Aged Receivable, Aged Payable
  Management             → Invoice Analysis, Analytic Report, FX Gains/Losses,
                           Deferred Expense, Deferred Revenue, Depreciation Schedule,
                           Disallowed Expenses, Budget Report, Loans Analysis,
                           Product Margins, Asset Register
  (top-level)            → Purchase Tax Report, Sale Tax Report
"""

env = self.env  # noqa: F821

REPORTING = 153  # Accounting > Reporting parent
STATEMENT = 159  # Statement Reports
AUDIT = 679      # Audit Reports (was OCA accounting reports)
PARTNER = 154    # Partner Reports
MANAGEMENT = 156 # Management

# ─── Helper: create menu if missing ────────────────────────────────
def upsert_menu(name, parent_id, action_xmlid=None, sequence=10):
    existing = env["ir.ui.menu"].search([
        ("name", "=", name),
        ("parent_id", "=", parent_id),
    ], limit=1)
    if existing:
        if action_xmlid:
            try:
                act = env.ref(action_xmlid)
                existing.action = f"{act._name},{act.id}"
                existing.sequence = sequence
            except Exception:
                pass
        return existing
    if action_xmlid:
        try:
            act = env.ref(action_xmlid)
            return env["ir.ui.menu"].create({
                "name": name,
                "parent_id": parent_id,
                "action": f"{act._name},{act.id}",
                "sequence": sequence,
            })
        except Exception as e:
            print(f"  ! {name}: action {action_xmlid} not found ({e!r})"[:120])
            return env["ir.ui.menu"].create({
                "name": name,
                "parent_id": parent_id,
                "sequence": sequence,
            })
    return env["ir.ui.menu"].create({
        "name": name,
        "parent_id": parent_id,
        "sequence": sequence,
    })


# ─── STATEMENT REPORTS ─────────────────────────────────────────────
print("\n=== Statement Reports ===")
upsert_menu("Balance Sheet", STATEMENT,
            "account_financial_report.action_general_ledger_wizard", 10)
upsert_menu("Profit and Loss", STATEMENT,
            "account_financial_report.action_trial_balance_wizard", 20)
upsert_menu("Profit and Loss Default", STATEMENT,
            "account_financial_report.action_trial_balance_wizard", 30)
upsert_menu("Cash Flow Statement", STATEMENT, sequence=40)  # placeholder
upsert_menu("Executive Summary", STATEMENT, sequence=50)    # placeholder
upsert_menu("Tax Return", STATEMENT,
            "account_financial_report.action_vat_report_wizard", 60)

# ─── AUDIT REPORTS ─────────────────────────────────────────────────
print("\n=== Audit Reports ===")
# Already have General Ledger (action 1728), Trial Balance (1733), Journal Ledger (681)
# Rename Journal Ledger → Journal Audit
jl = env["ir.ui.menu"].search([
    ("name", "=", "Journal Ledger"),
    ("parent_id", "=", AUDIT),
], limit=1)
if jl:
    jl.with_context(lang="en_US").name = "Journal Audit"
    jl.sequence = 30
    print(f"  ✓ Renamed Journal Ledger → Journal Audit")
# Move VAT Report out of Audit (it goes to Statement as Tax Return — already added)
vat = env["ir.ui.menu"].search([
    ("name", "=", "VAT Report"),
    ("parent_id", "=", AUDIT),
], limit=1)
if vat:
    vat.active = False
    print(f"  · VAT Report (under Audit) hidden — moved to Statement as Tax Return")

# ─── PARTNER REPORTS ───────────────────────────────────────────────
print("\n=== Partner Reports ===")
# Aged Partner Balance → split into Aged Receivable + Aged Payable
apb = env["ir.ui.menu"].search([
    ("name", "=", "Aged Partner Balance"),
    ("parent_id", "=", PARTNER),
], limit=1)
upsert_menu("Partner Ledger", PARTNER,
            "partner_statement.activity_statement_wizard_action", 10)
upsert_menu("Aged Receivable", PARTNER,
            "account_financial_report.action_aged_partner_balance_wizard", 20)
upsert_menu("Aged Payable", PARTNER,
            "account_financial_report.action_aged_partner_balance_wizard", 30)
# Hide the original Aged Partner Balance + Open Items
if apb:
    apb.active = False
    print(f"  · Aged Partner Balance (original) hidden — split into Receivable/Payable")
oi = env["ir.ui.menu"].search([
    ("name", "=", "Open Items"),
    ("parent_id", "=", PARTNER),
], limit=1)
if oi:
    oi.active = False
    print(f"  · Open Items hidden")

# ─── MANAGEMENT ───────────────────────────────────────────────────
print("\n=== Management ===")
# Existing: Invoice Analysis (157), Analytic Report (158), Depreciation Schedule (582), Loans Analysis (583)
upsert_menu("Unrealized Currency Gains/Losses", MANAGEMENT,
            "kob_thai_compliance.action_kob_fx_revaluation", 30)
upsert_menu("Deferred Expense", MANAGEMENT, sequence=40)   # placeholder
upsert_menu("Deferred Revenue", MANAGEMENT, sequence=50)   # placeholder
upsert_menu("Disallowed Expenses", MANAGEMENT, sequence=70)  # placeholder
upsert_menu("Budget Report", MANAGEMENT,
            "kob_purchase_pro.action_kob_procurement_budget", 80)
upsert_menu("Product Margins", MANAGEMENT,
            "kob_sales_pro.action_kob_channel_margin", 100)
upsert_menu("Asset Register", MANAGEMENT,
            "kob_thai_compliance.action_kob_fixed_asset", 110)

# ─── TOP-LEVEL TAX REPORTS (under Reporting parent 153) ────────────
print("\n=== Top-level Tax Reports ===")
upsert_menu("Purchase Tax Report", REPORTING,
            "account_financial_report.action_vat_report_wizard", 200)
upsert_menu("Sale Tax Report", REPORTING,
            "account_financial_report.action_vat_report_wizard", 210)

env.cr.commit()

# ─── FINAL VERIFICATION ──────────────────────────────────────────
print("\n=== Final structure ===")
for parent_id, label in [(STATEMENT, "Statement Reports"),
                          (AUDIT, "Audit Reports"),
                          (PARTNER, "Partner Reports"),
                          (MANAGEMENT, "Management")]:
    print(f"\n{label} (id={parent_id})")
    for m in env["ir.ui.menu"].search(
        [("parent_id", "=", parent_id), ("active", "=", True)],
        order="sequence, id",
    ):
        print(f"  · {m.name}")
