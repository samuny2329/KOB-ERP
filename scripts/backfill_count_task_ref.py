"""One-shot backfill: move legacy ABC labels from name → abc_label, then
assign a sequence-based reference to name. Run via:

    docker exec kob-odoo-19 odoo shell -c /etc/odoo/odoo.conf -d kobdb \
        --no-http < scripts/backfill_count_task_ref.py
"""
Task = env["wms.count.task"]
Sequence = env["ir.sequence"]

# Heuristic: legacy ABC-generated tasks have names starting with "[A] "/"[B] "/"[C] "
legacy = Task.search([
    "|", "|",
    ("name", "=like", "[A] %"),
    ("name", "=like", "[B] %"),
    ("name", "=like", "[C] %"),
])
print(f"Backfilling {len(legacy)} legacy task(s)...")
for t in legacy:
    new_ref = Sequence.next_by_code("wms.count.task") or t.name
    t.write({
        "abc_label": t.name,
        "name": new_ref,
    })
    print(f"  - id={t.id}: {t.abc_label} → {t.name}")

env.cr.commit()
print("Done.")
