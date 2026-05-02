env = self.env  # noqa: F821

# Move OCA reports into the proper Statement / Audit / Partner sections
PARTNER_REPORTS = 154   # Reporting > Partner Reports
STATEMENT_REPORTS = 159 # Reporting > Statement Reports
OCA_REPORTS = 679       # OCA accounting reports → repurpose as "Audit Reports"

# Step 1: Rename OCA parent → Audit Reports
oca_parent = env["ir.ui.menu"].browse(OCA_REPORTS)
oca_parent.with_context(lang="en_US").name = "Audit Reports"
oca_parent.sequence = 30
print(f"  ✓ Renamed menu #{OCA_REPORTS} → 'Audit Reports' (sequence 30)")

# Step 2: Move Aged Partner Balance + Open Items → Partner Reports
moves = {
    "Aged Partner Balance": PARTNER_REPORTS,
    "Open Items":           PARTNER_REPORTS,
}
for menu_name, new_parent in moves.items():
    m = env["ir.ui.menu"].search([
        ("name", "=", menu_name),
        ("parent_id", "=", OCA_REPORTS),
    ], limit=1)
    if m:
        m.parent_id = new_parent
        print(f"  ✓ Moved '{menu_name}' → Partner Reports")

env.cr.commit()

# Final verification
print("\n=== Inventory > Reporting structure ===")
for section in [STATEMENT_REPORTS, 154, OCA_REPORTS]:
    parent = env["ir.ui.menu"].browse(section)
    print(f"\n  {parent.name} (id={section})")
    for child in env["ir.ui.menu"].search(
        [("parent_id", "=", section), ("active", "=", True)],
        order="sequence, id",
    ):
        print(f"    · {child.name}")
