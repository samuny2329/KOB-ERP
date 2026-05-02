# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Backup Automation",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Tools",
    "summary": "Daily DB dump + retention + log",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/backup_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
