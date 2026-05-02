env = self.env  # noqa: F821 — odoo shell

# Re-activate native Physical Inventory menu disabled by OCA stock_inventory
m = env["ir.ui.menu"].browse(245)
print(f"Menu #{m.id}: {m.name} | active={m.active}")
m.active = True
env.cr.commit()
print(f"  ✓ now active={m.active}")

# Clear cache so browser sees the change
env["ir.ui.menu"].clear_caches()
env.cr.commit()
print("  ✓ menu cache cleared")
