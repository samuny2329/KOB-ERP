# -*- coding: utf-8 -*-
"""Phase 30 — Multi-channel notification framework.

Models:
  - kob.notification.channel : email / Line OA / SMS / Slack webhook
  - kob.notification.log     : every dispatch attempt
"""
import json
import logging
import requests
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class KobNotificationChannel(models.Model):
    _name = "kob.notification.channel"
    _description = "Notification Channel"

    name = fields.Char(required=True)
    channel_type = fields.Selection(
        [
            ("email", "Email"),
            ("line_oa", "Line Official Account"),
            ("sms", "SMS"),
            ("slack", "Slack Webhook"),
            ("teams", "Teams Webhook"),
        ],
        required=True,
    )
    endpoint_url = fields.Char(help="Webhook URL or API endpoint")
    auth_token = fields.Char(help="Bearer / Channel access token")
    sender_id = fields.Char(help="From email or sender ID")
    active = fields.Boolean(default=True)

    def send(self, subject, body, recipients=None):
        """Generic send — dispatcher per channel_type."""
        for ch in self:
            success, response = False, ""
            try:
                if ch.channel_type == "line_oa":
                    r = requests.post(
                        ch.endpoint_url or "https://api.line.me/v2/bot/message/broadcast",
                        headers={
                            "Authorization": f"Bearer {ch.auth_token}",
                            "Content-Type": "application/json",
                        },
                        json={"messages": [{"type": "text", "text": body}]},
                        timeout=15,
                    )
                    success = r.ok
                    response = r.text[:5000]
                elif ch.channel_type in ("slack", "teams"):
                    r = requests.post(
                        ch.endpoint_url,
                        json={"text": f"*{subject}*\n{body}"},
                        timeout=15,
                    )
                    success = r.ok
                    response = r.text[:5000]
                elif ch.channel_type == "email":
                    # Use Odoo's mail.mail
                    self.env["mail.mail"].create({
                        "subject": subject,
                        "body_html": body,
                        "email_from": ch.sender_id or "noreply@kissofbeauty.co.th",
                        "email_to": ", ".join(recipients or []),
                    }).send()
                    success = True
                    response = "Sent via Odoo mail"
                elif ch.channel_type == "sms":
                    # Placeholder: requires SMS gateway
                    response = "SMS placeholder — integrate gateway"
                    success = False
            except Exception as e:
                response = str(e)[:5000]
                success = False
            self.env["kob.notification.log"].sudo().create({
                "channel_id": ch.id,
                "subject": subject,
                "body": body[:5000],
                "success": success,
                "response": response,
            })


class KobNotificationLog(models.Model):
    _name = "kob.notification.log"
    _description = "Notification Log"
    _order = "create_date desc"

    channel_id = fields.Many2one("kob.notification.channel", ondelete="cascade")
    subject = fields.Char()
    body = fields.Text()
    success = fields.Boolean()
    response = fields.Text()
    create_date = fields.Datetime(readonly=True)
