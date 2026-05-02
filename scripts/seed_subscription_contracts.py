"""Seed sample subscription contract templates + sample contracts.

KOB cosmetic subscriptions:
  - "KOB Skincare Refill Monthly"  — base template, monthly billing
  - "MALISSA Daily Bundle Quarterly" — high-value quarterly
  - "KISS-MY-BODY VIP Annual"   — yearly with discount

Plus 3 sample customer contracts on real partners.
"""
import datetime
env = self.env  # noqa: F821

# ─── 1. Templates ─────────────────────────────────────────────────
TEMPLATES = [
    {
        "name": "KOB Skincare Refill Monthly",
        "recurring_rule_type": "monthly",
        "recurring_interval": 1,
    },
    {
        "name": "MALISSA Daily Bundle Quarterly",
        "recurring_rule_type": "monthly",
        "recurring_interval": 3,
    },
    {
        "name": "KISS-MY-BODY VIP Annual",
        "recurring_rule_type": "yearly",
        "recurring_interval": 1,
    },
]

ContractTemplate = env["contract.template"]
created_templates = []
for tmpl in TEMPLATES:
    existing = ContractTemplate.search([("name", "=", tmpl["name"])], limit=1)
    if existing:
        print(f"  · {tmpl['name']}: already exists")
        created_templates.append(existing)
        continue
    try:
        ct = ContractTemplate.create({
            "name": tmpl["name"],
            "contract_type": "sale",
            "company_id": 1,
        })
        print(f"  ✓ Template: {tmpl['name']}")
        created_templates.append(ct)
    except Exception as e:
        print(f"  ! {tmpl['name']}: {e!r}"[:120])

env.cr.commit()

# ─── 2. Sample Customer Contracts ─────────────────────────────────
print("\nStep 2: Sample customer contracts")
Contract = env["contract.contract"]

# Pick 3 sample partners
partners = env["res.partner"].search(
    [("customer_rank", ">", 0), ("active", "=", True)],
    limit=3,
)
if not partners:
    partners = env["res.partner"].search([("active", "=", True)], limit=3)

# Pick 3 sample products (real KOB SKUs)
products = env["product.product"].search([
    ("default_code", "in", ("KOB303", "AVH290", "DUT300")),
])

today = datetime.date.today()
created = 0
for i, (partner, tmpl) in enumerate(zip(partners, created_templates)):
    name = f"SUB-{today.year}-{partner.id:04d}-{tmpl.name[:20]}"
    if Contract.search([("name", "=", name)], limit=1):
        continue
    try:
        contract = Contract.create({
            "name": name,
            "partner_id": partner.id,
            "contract_template_id": tmpl.id,
            "contract_type": "sale",
            "company_id": 1,
            "date_start": today,
            "recurring_next_date": today + datetime.timedelta(days=30),
            "line_recurrence": True,
        })
        # Add product line
        if products and i < len(products):
            product = products[i]
            env["contract.line"].create({
                "contract_id": contract.id,
                "product_id": product.id,
                "name": f"Monthly {product.name}",
                "quantity": 1,
                "price_unit": float(product.list_price or 100),
                "uom_id": product.uom_id.id,
                "recurring_rule_type": "monthly",
                "recurring_interval": 1,
                "date_start": today,
                "recurring_next_date": today + datetime.timedelta(days=30),
            })
        created += 1
        print(f"  ✓ {name} (partner: {partner.name})")
    except Exception as e:
        print(f"  ! {name}: {e!r}"[:120])

env.cr.commit()
print(f"\n✓ {created} sample contracts created")

# ─── Summary ──────────────────────────────────────────────────────
print("\n=== Summary ===")
print(f"  Templates: {ContractTemplate.search_count([])}")
print(f"  Active contracts: {Contract.search_count([('active','=',True)])}")
print(f"  Customer contracts: {Contract.search_count([('contract_type','=','sale')])}")
