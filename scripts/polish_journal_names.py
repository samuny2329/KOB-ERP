env = self.env  # odoo shell

inv = env["account.journal"].browse(1)
bill = env["account.journal"].browse(2)
inv.with_context(lang="en_US").name = "Customer Invoices"
bill.with_context(lang="en_US").name = "Vendor Bills"

bnk1 = env["account.journal"].search(
    [("code", "=", "BNK1"), ("company_id", "=", 1)], limit=1,
)
if bnk1:
    bnk1.show_on_dashboard = False

env.cr.commit()
print(f"  · Renamed INV → Customer Invoices, BILL → Vendor Bills")
print(f"  · BNK1 hidden from dashboard")

print("\nFinal dashboard journal list:")
for j in env["account.journal"].search(
    [("company_id", "=", 1), ("show_on_dashboard", "=", True)],
    order="type, sequence, id",
):
    print(f"  {j.code:6s} {j.type:8s} | {j.name}")
