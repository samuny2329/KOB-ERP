# -*- coding: utf-8 -*-
"""Catch outgoing mail errors during user invitation, conversion etc.
Convert hard error to a friendly warning notification."""
import logging
from odoo import _, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    def action_reset_password(self):
        """Wrap base action_reset_password — show warning instead of
        crashing when mail server is unreachable / unconfigured."""
        try:
            return super().action_reset_password()
        except Exception as e:
            _logger.warning("Mail send failed in action_reset_password: %s", e)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Mail Server Not Available"),
                    "message": _(
                        "ไม่สามารถส่งอีเมลได้ — กรุณาตั้งค่า "
                        "Settings → Technical → Outgoing Mail Servers "
                        "(SMTP) หรือแจ้ง user ให้ตั้งรหัสเอง"),
                    "type": "warning",
                    "sticky": True,
                },
            }
