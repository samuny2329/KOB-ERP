{
    "name": "KOB ERP — Mail Server Optional (graceful)",
    "version": "19.0.1.0.0",
    "summary": ("Catch outgoing mail errors and convert to friendly "
                "warnings; seed placeholder SMTP server for setup."),
    "category": "Mail",
    "depends": ["base", "mail"],
    "data": [
        "data/mail_server_placeholder.xml",
    ],
    "installable": True,
    "auto_install": False,
}
