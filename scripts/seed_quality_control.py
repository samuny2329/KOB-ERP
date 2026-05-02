"""Seed Quality Control test categories + tests + sample inspection.

Categories:
  - Incoming QC (raw material check)
  - Production QC (in-process)
  - Outgoing QC (finished goods)
  - Customer Return QC (RMA inspection)

Sample tests:
  - Visual Inspection (qualitative)
  - Weight Check (quantitative ±5g)
  - pH Test (quantitative 4.5-7.5)
  - Microbial Count (quantitative ≤100 CFU/g)
"""
env = self.env  # noqa: F821

# 1. Categories
CATEGORIES = [
    "Incoming QC (Raw Material)",
    "In-Process QC (Production)",
    "Outgoing QC (Finished Goods)",
    "Customer Return QC (RMA)",
]
for c in CATEGORIES:
    if not env["qc.test.category"].search([("name", "=", c)], limit=1):
        env["qc.test.category"].create({"name": c})
        print(f"  ✓ Category: {c}")

env.cr.commit()
cat_map = {c.name: c for c in env["qc.test.category"].search([])}

# 2. Tests
TESTS = [
    {
        "name": "Visual Inspection — Finished Goods",
        "category_id": cat_map["Outgoing QC (Finished Goods)"].id,
        "active": True,
        "questions": [
            ("Packaging intact (no damage)?", "qualitative"),
            ("Label clear & correct?",         "qualitative"),
            ("Color matches reference?",        "qualitative"),
            ("No leakage from container?",      "qualitative"),
        ],
    },
    {
        "name": "Weight Check — Finished Goods",
        "category_id": cat_map["Outgoing QC (Finished Goods)"].id,
        "active": True,
        "questions": [
            ("Net weight (g)?", "quantitative"),
        ],
    },
    {
        "name": "pH Test — Lotion / Cream",
        "category_id": cat_map["In-Process QC (Production)"].id,
        "active": True,
        "questions": [
            ("pH value?", "quantitative"),
        ],
    },
    {
        "name": "RM Visual + Weight",
        "category_id": cat_map["Incoming QC (Raw Material)"].id,
        "active": True,
        "questions": [
            ("Container sealed & undamaged?", "qualitative"),
            ("CoA present from supplier?",    "qualitative"),
            ("Total weight matches PO?",      "quantitative"),
        ],
    },
    {
        "name": "RMA Inspection",
        "category_id": cat_map["Customer Return QC (RMA)"].id,
        "active": True,
        "questions": [
            ("Item complete?",         "qualitative"),
            ("Damage observed?",       "qualitative"),
            ("Lot/Batch matches AWB?", "qualitative"),
        ],
    },
]

created = 0
for t in TESTS:
    existing = env["qc.test"].search([("name", "=", t["name"])], limit=1)
    if existing:
        continue
    test = env["qc.test"].create({
        "name": t["name"],
        "category": t["category_id"],
        "active": t["active"],
    })
    for qstr, qtype in t["questions"]:
        env["qc.test.question"].create({
            "name": qstr,
            "test": test.id,
            "type": qtype,
            "min_value": 0.0 if qtype == "quantitative" else False,
            "max_value": 1000.0 if qtype == "quantitative" else False,
        })
    created += 1
    print(f"  ✓ Test: {t['name']} ({len(t['questions'])} questions)")

env.cr.commit()

# Summary
print(f"\n=== Final ===")
print(f"  Categories: {env['qc.test.category'].search_count([])}")
print(f"  Tests:      {env['qc.test'].search_count([])}")
print(f"  Questions:  {env['qc.test.question'].search_count([])}")
