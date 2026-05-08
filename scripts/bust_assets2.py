"""Find + delete all asset bundle attachments (any naming pattern)."""
A = env["ir.attachment"]  # noqa: F821
patterns = ["/web/assets/%", "web.assets_%", "%.assets_%.js", "%.assets_%.css"]
total = 0
for p in patterns:
    recs = A.search([("name", "=like", p)])
    print(f"  pattern '{p}': {len(recs)} records")
    if recs:
        # Show samples
        for r in recs[:3]:
            print(f"    sample: {r.name}")
        recs.unlink()
        total += len(recs)
env.cr.commit()  # noqa: F821
print(f"Deleted total: {total}")
