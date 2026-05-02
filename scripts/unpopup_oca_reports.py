env = self.env  # noqa: F821

# Change all OCA report wizards from popup ('new') to full-page ('current')
# So user fills the form on a full screen instead of overlay modal.
WIZARDS = [
    1727,  # action_aged_partner_balance_wizard
    1728,  # action_general_ledger_wizard
    1729,  # act_action_general_ledger_wizard_partner_relation
    1730,  # action_journal_ledger_wizard (Journal Audit)
    1731,  # action_open_items_wizard
    1732,  # act_action_open_items_wizard_partner_relation
    1733,  # action_trial_balance_wizard
    1734,  # action_vat_report_wizard (Tax Return / Purchase Tax / Sale Tax)
]

# Also include partner_statement wizards
ps_wizard_ids = env["ir.actions.act_window"].search([
    ("res_model", "in", (
        "activity.statement.wizard",
        "outstanding.statement.wizard",
        "detailed.activity.statement.wizard",
    )),
]).ids
WIZARDS += ps_wizard_ids

print(f"Total wizards to convert: {len(WIZARDS)}")
for aid in WIZARDS:
    a = env["ir.actions.act_window"].browse(aid)
    if a.exists() and a.target == "new":
        a.target = "current"
        print(f"  ✓ #{aid:5d} {a.name} → target=current")

env.cr.commit()
print("\n✓ All OCA report wizards now open full-page (no more popup modal)")
