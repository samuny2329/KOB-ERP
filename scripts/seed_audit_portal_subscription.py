"""Phase 25-27: configure auditlog rules + portal access + subscription cron."""
env = self.env  # noqa: F821

# ─── PHASE 25 — Audit rules ─────────────────────────────────────
print("=== Phase 25: Audit Rules ===")
RULES = [
    "purchase.order",
    "sale.order",
    "account.move",
    "account.payment",
    "kob.fixed.asset",
    "kob.intercompany.loan",
    "kob.payslip",
    "kob.tax.cert.annual",
    "kob.procurement.budget",
    "stock.quant",
]
for model_name in RULES:
    model = env["ir.model"].search([("model", "=", model_name)], limit=1)
    if not model:
        continue
    existing = env["auditlog.rule"].search([("model_id", "=", model.id)], limit=1)
    if existing:
        continue
    try:
        env["auditlog.rule"].create({
            "name": f"Audit — {model_name}",
            "model_id": model.id,
            "log_type": "full",
            "log_create": True,
            "log_write": True,
            "log_unlink": True,
            "state": "subscribed",
        })
        print(f"  ✓ Audit rule: {model_name}")
    except Exception as e:
        print(f"  ! {model_name}: {e!r}"[:120])

env.cr.commit()

# ─── PHASE 26 — Portal access for customers ─────────────────────
print("\n=== Phase 26: Customer Portal ===")
portal_group = env.ref("base.group_portal", raise_if_not_found=False)
if portal_group:
    print(f"  · Portal group exists: {portal_group.name} (id={portal_group.id})")
    portal_users = env["res.users"].search_count([
        ("group_ids" if "group_ids" in env["res.users"]._fields else "groups_id", "in", portal_group.id),
    ])
    print(f"  · Portal users: {portal_users}")

# Sample: grant portal access to first 3 customer partners (with email)
candidates = env["res.partner"].search([
    ("customer_rank", ">", 0),
    ("email", "!=", False),
    ("is_company", "=", False),
], limit=3)
print(f"  · Top 3 customer candidates with email:")
for p in candidates:
    print(f"    {p.name} <{p.email}>")
print("  ℹ️  To grant portal access: Contacts → Action menu → Grant Portal Access")

# ─── PHASE 27 — Subscription auto-renewal cron ──────────────────
print("\n=== Phase 27: Subscription Auto-renewal ===")
contracts = env["contract.contract"].search([
    ("active", "=", True),
    ("contract_type", "=", "sale"),
])
print(f"  · Active customer contracts: {len(contracts)}")
# OCA contract has built-in cron for invoicing — verify it exists
existing_cron = env["ir.cron"].search([
    ("cron_name", "ilike", "%recurring%invoice%contract%"),
])
print(f"  · Recurring invoice crons: {len(existing_cron)}")
for c in existing_cron[:3]:
    print(f"    {c.cron_name} (active={c.active}, next={c.nextcall})")

env.cr.commit()
print("\n=== Done ===")
print(f"  Audit rules: {env['auditlog.rule'].search_count([])}")
