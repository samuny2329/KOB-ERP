# -*- coding: utf-8 -*-
from odoo import models

from ..hooks import KOB_DATE_FORMAT, KOB_TIME_FORMAT


class ResLang(models.Model):
    _inherit = "res.lang"

    def _activate_lang(self, code):
        """Newly-activated languages also get the KOB format."""
        lang = super()._activate_lang(code)
        if lang:
            vals = {}
            if lang.date_format != KOB_DATE_FORMAT:
                vals["date_format"] = KOB_DATE_FORMAT
            if lang.time_format != KOB_TIME_FORMAT:
                vals["time_format"] = KOB_TIME_FORMAT
            if vals:
                lang.write(vals)
        return lang
