# -*- coding: utf-8 -*-
"""On install: point every existing user's default landing to the KOB ERP
welcome dashboard so the first thing they see after login is the module
overview with descriptions."""

from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _kob_set_welcome_landing(self):
        """Idempotent — re-callable on each addon update."""
        action = self.env.ref("kob_base.action_kob_welcome", raise_if_not_found=False)
        if not action:
            return
        # Apply only to humans (skip portal / public / __system__).
        users = self.search([
            ("share", "=", False),
            ("login", "not in", ("__system__", "portal", "public")),
        ])
        users.write({"action_id": action.id})
