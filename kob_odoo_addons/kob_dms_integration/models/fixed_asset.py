# -*- coding: utf-8 -*-
from odoo import models


class KobFixedAsset(models.Model):
    _name = "kob.fixed.asset"
    _inherit = ["kob.fixed.asset", "kob.dms.mixin"]
    _dms_parent_folder = "Assets"

    def _get_dms_label(self):
        self.ensure_one()
        return self.asset_code or self.name or f"ASSET-{self.id}"
