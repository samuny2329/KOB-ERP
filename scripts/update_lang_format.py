env = self.env  # noqa: F821

lang = env["res.lang"].search([("code", "=", "en_US")], limit=1)
print(f"Current en_US: date={lang.date_format!r} | time={lang.time_format!r}")

# DD/MM/YYYY HH:MM:SS — Thai / European convention, 24-hour
# Combined render example: "02/05/2026 18:52:53"
lang.write({
    "date_format": "%d/%m/%Y",
    "time_format": "%H:%M:%S",
    "week_start": "1",  # Monday
    "decimal_point": ".",
    "thousands_sep": ",",
    "grouping": "[3,0]",
})
print(f"Updated  en_US: date={lang.date_format!r} | time={lang.time_format!r}")

env.cr.commit()
print("\n✓ Timestamps will now render as: 02/05/2026 18:52:53 (DD/MM/YYYY 24h)")
