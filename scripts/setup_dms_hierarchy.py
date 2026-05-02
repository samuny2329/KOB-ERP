"""Set up DMS storage + directory hierarchy for KOB.

Storage: KOB Document Storage (database, then can switch to filesystem)
Directories:
  📁 KOB Documents
    ├─ 📁 Vendors        (vendor agreements, certificates, NDAs)
    ├─ 📁 Customers      (contracts, orders, complaints)
    ├─ 📁 Employees      (CV, contracts, training certs, ID copies)
    ├─ 📁 Assets         (purchase invoices, warranty, photos)
    ├─ 📁 Compliance     (audit, BOI, RD, SSO)
    ├─ 📁 Marketing      (campaign briefs, creative assets)
    └─ 📁 Operations     (SOP, manuals, policies)
"""
env = self.env  # noqa: F821

# 1. Create default storage
storage = env["dms.storage"].search([("name", "=", "KOB Documents Storage")], limit=1)
if not storage:
    storage = env["dms.storage"].create({
        "name": "KOB Documents Storage",
        "save_type": "database",  # can switch to 'file' later
        "company_id": 1,
        "is_hidden": False,
    })
    print(f"  ✓ Storage created: {storage.name}")

# 2. Root directory
root = env["dms.directory"].search(
    [("name", "=", "KOB Documents"), ("is_root_directory", "=", True)],
    limit=1,
)
if not root:
    root = env["dms.directory"].create({
        "name": "KOB Documents",
        "is_root_directory": True,
        "storage_id": storage.id,
        "company_id": 1,
    })
    print(f"  ✓ Root: {root.name}")

# 3. Sub-directories
SUBDIRS = [
    ("Vendors", "vendor agreements, certificates, NDAs"),
    ("Customers", "customer contracts, complaints, returns"),
    ("Employees", "CVs, employment contracts, training, ID copies"),
    ("Assets", "purchase invoices, warranties, asset photos"),
    ("Compliance", "audit reports, BOI, RD, SSO filings"),
    ("Marketing", "campaign briefs, creative assets, brand guidelines"),
    ("Operations", "SOPs, manuals, internal policies"),
]
for name, desc in SUBDIRS:
    sub = env["dms.directory"].search([
        ("name", "=", name), ("parent_id", "=", root.id),
    ], limit=1)
    if not sub:
        env["dms.directory"].create({
            "name": name,
            "parent_id": root.id,
            "is_root_directory": False,
            "company_id": 1,
        })
        print(f"  ✓ Sub: {name}")
    else:
        print(f"  · {name} exists")

env.cr.commit()

# 4. Categories (cross-cutting tags)
CATEGORIES = [
    "Contract", "Invoice", "Receipt", "Certificate",
    "Photo", "Manual", "Policy", "Tax Document",
]
for cat_name in CATEGORIES:
    if not env["dms.category"].search([("name", "=", cat_name)], limit=1):
        env["dms.category"].create({"name": cat_name})
        print(f"  ✓ Category: {cat_name}")

env.cr.commit()

# Summary
print("\n=== Final ===")
print(f"  Storages: {env['dms.storage'].search_count([])}")
print(f"  Directories: {env['dms.directory'].search_count([])}")
print(f"  Categories: {env['dms.category'].search_count([])}")
print(f"\n  Tree:")
for d in env["dms.directory"].search([("is_root_directory", "=", True)]):
    print(f"    📁 {d.name}")
    for sub in env["dms.directory"].search([("parent_id", "=", d.id)], order="name"):
        print(f"      └─ 📁 {sub.name}")
