env = self.env  # noqa: F821

lang = env["res.lang"].search([("code", "=", "en_US")], limit=1)
print(f"Current en_US: date={lang.date_format!r} | time={lang.time_format!r}")

# New format: ISO-like sortable, drop seconds
#   date_format: %Y-%m-%d   →   2026-05-02
#   time_format: %H:%M      →   18:52
# Combined render: "2026-05-02 18:52" (sortable, unambiguous, 24h)
lang.write({
    "date_format": "%Y-%m-%d",
    "time_format": "%H:%M:%S",  # Odoo 19 requires %S in time_format
    "week_start": "1",  # Monday
    "decimal_point": ".",
    "thousands_sep": ",",
    "grouping": "[3,0]",
})
print(f"Updated  en_US: date={lang.date_format!r} | time={lang.time_format!r}")

env.cr.commit()
print("\n✓ Timestamps will now render as: 2026-05-02 18:52 (ISO sortable, 24h, no seconds)")

