# -*- coding: utf-8 -*-
"""QWeb format helpers — enforce KOB date format in QWeb reports.

Odoo's QWeb evaluates `format_date(value)` / `format_datetime(value)` via
``odoo.tools.format_date`` / ``format_datetime``, which pull format strings
from ``res.lang.date_format`` / ``time_format``. Setting those fields (done
by hooks.set_kob_lang_formats) covers most cases.

This module additionally pins the format strings passed to ``babel`` when
the caller leaves ``date_format`` / ``time_format`` unspecified, by
overriding the QWeb context values used in PDF reports.
"""
from odoo import models

from ..hooks import KOB_DATE_FORMAT, KOB_TIME_FORMAT


class IrQweb(models.AbstractModel):
    _inherit = "ir.qweb"

    def _prepare_environment(self, values):
        """Inject KOB date/time format strings into the QWeb context."""
        result = super()._prepare_environment(values)
        # ``values`` is mutated by super(); we add fallback formats so any
        # template using ``format_date(d, date_format=ctx.kob_date_format)``
        # picks up the canonical KOB format.
        values.setdefault("kob_date_format", KOB_DATE_FORMAT)
        values.setdefault("kob_time_format", KOB_TIME_FORMAT)
        return result
