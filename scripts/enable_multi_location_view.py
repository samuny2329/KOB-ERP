#!/usr/bin/env python3
"""Enable Multi-Location + Push/Pull groups so delivery orders show child bins.

After this, on every stock.picking (Delivery Order, Internal Transfer, etc.):
  - The Operations / Detailed Operations table shows a 'From' column
  - Each move line drills into the specific child bin (e.g. K-On/Stock/PF-A-1-01)
    where Odoo found stock to reserve, instead of showing only the parent
    K-On/Stock at the header level.
"""

env = self.env  # noqa: F821

multi = env.ref("stock.group_stock_multi_locations")
adv = env.ref("stock.group_adv_location")
internal = env.ref("base.group_user")

print(f"group_stock_multi_locations id: {multi.id}")
print(f"group_adv_location id: {adv.id}")
print(f"base.group_user id: {internal.id}")

# Add as implied groups so every internal user inherits them
internal.write({
    "implied_ids": [(4, multi.id), (4, adv.id)],
})
env.cr.commit()
print("\n✓ multi-location + advanced location flow enabled for all internal users")

# Verify
n_users = env["res.users"].search_count([])
n_with_multi = env.cr.execute(
    "SELECT COUNT(DISTINCT uid) FROM res_groups_users_rel WHERE gid = %s",
    (multi.id,),
)
multi_count = env.cr.fetchone()[0]
print(f"Users with multi-location group: {multi_count}/{n_users}")
