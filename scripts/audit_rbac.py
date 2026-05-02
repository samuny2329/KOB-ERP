"""Phase 38 — RBAC Audit. Print group → permissions map for each app."""
env = self.env  # noqa: F821

print("\n=== KOB RBAC Audit ===\n")

# 1. KOB-specific groups
KOB_GROUPS = env["res.groups"].search([
    "|", ("name", "ilike", "kob"), ("name", "ilike", "wms"),
])
print(f"KOB-related groups: {len(KOB_GROUPS)}")
for g in KOB_GROUPS:
    n_users = env["res.users"].search_count([
        ("group_ids" if "group_ids" in env["res.users"]._fields else "groups_id", "in", g.id),
    ])
    n_acl = env["ir.model.access"].search_count([("group_id", "=", g.id)])
    print(f"  {g.name:50s} | users: {n_users:3d} | model.access rules: {n_acl:3d}")

# 2. Models that are world-readable (no group restriction)
print(f"\nModels with NO ACL (world readable):")
env.cr.execute("""
    SELECT m.model
    FROM ir_model m
    WHERE m.model LIKE 'kob.%'
      AND NOT EXISTS (
        SELECT 1 FROM ir_model_access a
        WHERE a.model_id = m.id
      )
    ORDER BY m.model
""")
for row in env.cr.fetchall():
    print(f"  ⚠️  {row[0]}")

# 3. Admin users
print(f"\nAdmin users (group_system):")
admin_group = env.ref("base.group_system")
admin_users = env["res.users"].search([
    ("group_ids" if "group_ids" in env["res.users"]._fields else "groups_id", "in", admin_group.id),
])
for u in admin_users[:10]:
    print(f"  · {u.login:40s} {u.name}")

# 4. Total user count
print(f"\nTotal active users: {env['res.users'].search_count([('active','=',True)])}")
print(f"Total kob.* models: {env['ir.model'].search_count([('model','like','kob.%')])}")
print(f"Total ACL rules:    {env['ir.model.access'].search_count([])}")
