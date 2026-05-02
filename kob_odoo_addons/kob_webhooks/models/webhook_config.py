# -*- coding: utf-8 -*-
"""KOB Webhooks — outgoing HTTP POST on Odoo events.

Config:
  - Subscribe to model + trigger event (create / write / unlink / state-change)
  - Target URL + auth header
  - Payload template (JSON via QWeb)

Log:
  - Every dispatch attempt: status code, response, retry count
"""
import json
import logging
import requests
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class KobWebhookConfig(models.Model):
    _name = "kob.webhook.config"
    _description = "Webhook Configuration"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        "ir.model", string="Source Model", required=True,
        ondelete="cascade",
        help="Watch events on this model.",
    )
    model_name = fields.Char(related="model_id.model", store=True, readonly=True)
    trigger = fields.Selection(
        [
            ("create", "On Create"),
            ("write",  "On Update"),
            ("unlink", "On Delete"),
            ("manual", "Manual Trigger Only"),
        ],
        default="create",
        required=True,
    )
    state_filter = fields.Char(
        help="Optional. JSON-formatted domain to filter records, "
             "e.g. [('state','=','done')]",
    )
    target_url = fields.Char(required=True, help="Full URL incl. https://")
    method = fields.Selection(
        [("POST","POST"),("PUT","PUT"),("PATCH","PATCH")],
        default="POST", required=True,
    )
    auth_header = fields.Char(
        help="Optional. e.g. 'Bearer abc123' or 'Basic <base64>'",
    )
    payload_template = fields.Text(
        default='{"id": {{record.id}}, "name": "{{record.display_name}}"}',
        help="JSON template, render with {{record.field}} variables.",
    )
    retry_max = fields.Integer(default=3)
    timeout_sec = fields.Integer(default=15)
    log_ids = fields.One2many("kob.webhook.log", "config_id", readonly=True)

    def action_test(self):
        """Manually fire a test webhook with sample payload."""
        self.ensure_one()
        payload = {"test": True, "config": self.name}
        try:
            r = requests.request(
                self.method, self.target_url,
                json=payload,
                headers={"Authorization": self.auth_header}
                       if self.auth_header else {},
                timeout=self.timeout_sec,
            )
            self.env["kob.webhook.log"].sudo().create({
                "config_id": self.id,
                "model_name": self.model_name,
                "record_id": 0,
                "trigger": "manual",
                "status_code": r.status_code,
                "response_body": r.text[:5000],
                "success": r.ok,
            })
        except Exception as e:
            self.env["kob.webhook.log"].sudo().create({
                "config_id": self.id,
                "model_name": self.model_name,
                "record_id": 0,
                "trigger": "manual",
                "status_code": 0,
                "response_body": str(e)[:5000],
                "success": False,
            })


class KobWebhookLog(models.Model):
    _name = "kob.webhook.log"
    _description = "Webhook Delivery Log"
    _order = "create_date desc"

    config_id = fields.Many2one("kob.webhook.config", ondelete="cascade")
    model_name = fields.Char()
    record_id = fields.Integer()
    trigger = fields.Char()
    status_code = fields.Integer()
    response_body = fields.Text()
    success = fields.Boolean()
    create_date = fields.Datetime(readonly=True)
