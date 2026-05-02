"""Seed KOB projects + link to existing CapEx/OpEx budgets.

Projects mirror Notion structure:
  - Brand Marketing — Q1/Q2/Q3/Q4 campaigns
  - Product Launch — new SKU launches
  - Operations — warehouse/IT/HR initiatives
  - R&D — new formulations
"""
import datetime
env = self.env  # noqa: F821

PROJECTS = [
    # (name, customer-facing?, color, allow_billable)
    ("MKT — KISS-MY-BODY Q1 New Year Bundle",  False, 1),
    ("MKT — MALISSA Songkran Glow Q2",         False, 2),
    ("MKT — SKINOXY Mid-Year Sale Q3",         False, 3),
    ("MKT — KOB Holiday Gift Sets Q4",         False, 4),
    ("LAUNCH — MALISSA Soothing Gel 290g",     False, 5),
    ("LAUNCH — SKINOXY Eye Cream 30ml",        False, 6),
    ("OPS — Warehouse Automation 2026",        False, 7),
    ("OPS — KPI Dashboard Rollout",            False, 8),
    ("HR — Annual KPI Assessment 2026",        False, 9),
    ("RND — New Cosmetic Formulation Lab",     False, 10),
    ("IT — KOB ERP Phase Rollout",             False, 11),
    ("FIN — FY26 Budget Tracking",             False, 12),
]

created = 0
for name, _, color in PROJECTS:
    if not env["project.project"].search([("name", "=", name)], limit=1):
        env["project.project"].create({
            "name": name,
            "active": True,
            "color": color,
            "company_id": 1,
        })
        created += 1
        print(f"  ✓ {name}")

env.cr.commit()

# Link existing FY2026 budgets to relevant projects
LINKS = {
    "MKT — KISS-MY-BODY Q1 New Year Bundle":   "OPEX-FY26-Marketing",
    "MKT — MALISSA Songkran Glow Q2":          "OPEX-FY26-Marketing",
    "OPS — Warehouse Automation 2026":         "CAPEX-FY26-Equipment",
    "OPS — KPI Dashboard Rollout":             "CAPEX-FY26-Software",
    "IT — KOB ERP Phase Rollout":              "CAPEX-FY26-IT Hardware",
    "RND — New Cosmetic Formulation Lab":      "OPEX-FY26-Professional",
    "HR — Annual KPI Assessment 2026":         "OPEX-FY26-Training",
}
linked = 0
for proj_name, budget_name in LINKS.items():
    proj = env["project.project"].search([("name", "=", proj_name)], limit=1)
    bud = env["kob.procurement.budget"].search([("name", "=", budget_name)], limit=1)
    if proj and bud:
        bud.project_id = proj.id
        linked += 1
        print(f"  ✓ Linked: {proj.name[:40]} → {bud.name}")

env.cr.commit()

print(f"\n=== Final ===")
print(f"  Projects created: {created}")
print(f"  Budget links:     {linked}")
print(f"  Total projects:   {env['project.project'].search_count([])}")
