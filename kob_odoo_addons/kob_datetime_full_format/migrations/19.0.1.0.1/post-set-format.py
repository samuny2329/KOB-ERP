# -*- coding: utf-8 -*-
"""Re-apply KOB date/time format on upgrade.

post_init_hook only runs on first install; this migration ensures every
``-u kob_datetime_full_format`` re-asserts the canonical format on every
res.lang record (in case a manual edit drifted them).
"""
from odoo.api import Environment


def migrate(cr, version):
    env = Environment(cr, 1, {})  # SUPERUSER
    from odoo.addons.kob_datetime_full_format.hooks import set_kob_lang_formats
    set_kob_lang_formats(env)
