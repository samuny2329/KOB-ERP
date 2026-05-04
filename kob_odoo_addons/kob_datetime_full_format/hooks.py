# -*- coding: utf-8 -*-
"""Post-install hook: enforce KOB date/time format on every res.lang."""

KOB_DATE_FORMAT = "%d/%m/%Y"
KOB_TIME_FORMAT = "%H:%M:%S"


def set_kob_lang_formats(env):
    """Force every active language to use the KOB date/time format.

    Runs at install + on every -u of this module.
    """
    Lang = env["res.lang"].sudo()
    langs = Lang.with_context(active_test=False).search([])
    for lang in langs:
        vals = {}
        if lang.date_format != KOB_DATE_FORMAT:
            vals["date_format"] = KOB_DATE_FORMAT
        if lang.time_format != KOB_TIME_FORMAT:
            vals["time_format"] = KOB_TIME_FORMAT
        if vals:
            lang.write(vals)
