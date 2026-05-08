"""Bust Odoo asset bundle cache so SCSS/JS changes show up.

Deletes ir.attachment rows where name starts with /web/assets/.
Odoo regenerates them on next page load.
"""
A = env["ir.attachment"]  # noqa: F821
matches = A.search([("name", "=like", "/web/assets/%")])
print(f"Deleting {len(matches)} cached asset attachments...")
matches.unlink()
env.cr.commit()  # noqa: F821
print("Done. Reload browser with Ctrl+Shift+R.")
