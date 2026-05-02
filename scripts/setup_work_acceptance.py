#!/usr/bin/env python3
"""Configure Work Acceptance (3-way matching) globally + on vendors.

Settings:
  1. Enable WA on Goods Receipt (group_enable_wa_on_in)
  2. Enforce WA on Vendor Bill (group_enforce_wa_on_invoice) — bill blocked
     until matching WA exists
  3. Add admin to all 3 enforcement groups so they can validate
"""

env = self.env  # noqa: F821

# Find groups
group_enable_in = env.ref(
    "purchase_work_acceptance.group_enable_wa_on_in", raise_if_not_found=False,
)
group_enforce_in = env.ref(
    "purchase_work_acceptance.group_enforce_wa_on_in", raise_if_not_found=False,
)
group_enable_inv = env.ref(
    "purchase_work_acceptance.group_enable_wa_on_invoice", raise_if_not_found=False,
)
group_enforce_inv = env.ref(
    "purchase_work_acceptance.group_enforce_wa_on_invoice", raise_if_not_found=False,
)
print("Groups located:")
for g in [group_enable_in, group_enforce_in, group_enable_inv, group_enforce_inv]:
    if g:
        print(f"  · {g.name} (id={g.id})")

# Imply WA-enable groups via base.group_user — every internal user gets them
internal = env.ref("base.group_user")
imply_ids = [g.id for g in [group_enable_in, group_enable_inv] if g]
if imply_ids:
    internal.write({
        "implied_ids": [(4, gid) for gid in imply_ids],
    })
    print(f"\n✓ enabled WA-on-receipt + WA-on-invoice for all internal users")

# Grant 'enforce' to admin only — purchase manager
admin = env.ref("base.user_admin", raise_if_not_found=False) or env.ref("base.user_root")
enforce_ids = [g.id for g in [group_enforce_in, group_enforce_inv] if g]
if enforce_ids:
    if "group_ids" in env["res.users"]._fields:
        admin.write({"group_ids": [(4, gid) for gid in enforce_ids]})
    else:
        admin.sudo().write({"groups_id": [(4, gid) for gid in enforce_ids]})
    print(f"✓ admin user granted WA-enforce groups")

env.cr.commit()

# Verification
print("\n=== WA group state ===")
for g in [group_enable_in, group_enforce_in, group_enable_inv, group_enforce_inv]:
    if g:
        n_users = env.cr.execute(
            "SELECT COUNT(*) FROM res_groups_users_rel WHERE gid = %s", (g.id,),
        )
        c = env.cr.fetchone()[0]
        print(f"  {g.name}: {c} users (direct)")
