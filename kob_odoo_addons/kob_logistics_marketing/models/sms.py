# -*- coding: utf-8 -*-
"""Phase 52 — SMS gateway integration."""
from odoo import api, fields, models, _


class KobSmsGateway(models.Model):
    _name = "kob.sms.gateway"
    _description = "SMS Gateway"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="thbulksms, twilio, infobip, ...")
    sequence = fields.Integer(default=10)
    api_endpoint = fields.Char()
    api_key = fields.Char()
    api_secret = fields.Char()
    sender_id = fields.Char(string="Sender ID", default="KOB")
    cost_per_msg = fields.Float(default=0.5, string="Cost / SMS (THB)")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("kob_sms_gateway_code_unique", "unique(code)",
         "Gateway code must be unique."),
    ]


class KobSmsBlast(models.Model):
    _name = "kob.sms.blast"
    _description = "SMS Blast"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    gateway_id = fields.Many2one("kob.sms.gateway", required=True)
    segment_id = fields.Many2one("kob.customer.segment", required=True)
    body = fields.Text(required=True,
                       help="Use {name} {first_name} placeholders")
    state = fields.Selection(
        [("draft", "Draft"),
         ("scheduled", "Scheduled"),
         ("sending", "Sending"),
         ("sent", "Sent"),
         ("cancelled", "Cancelled")],
        default="draft", tracking=True,
    )
    scheduled_at = fields.Datetime()
    sent_count = fields.Integer(readonly=True, default=0)
    failed_count = fields.Integer(readonly=True, default=0)
    estimated_cost = fields.Float(compute="_compute_cost", store=False)

    @api.depends("segment_id", "gateway_id")
    def _compute_cost(self):
        for r in self:
            n = r.segment_id and r.segment_id.member_count or 0
            r.estimated_cost = n * (r.gateway_id.cost_per_msg if r.gateway_id else 0)

    def action_send(self):
        Log = self.env["kob.sms.log"]
        for r in self:
            partners = r.segment_id.compute_partners()
            for p in partners:
                phone = p.mobile or p.phone
                if not phone:
                    continue
                msg = (r.body or "").format(
                    name=p.name or "", first_name=(p.name or "").split()[0]
                )
                Log.create({
                    "blast_id": r.id,
                    "partner_id": p.id,
                    "phone": phone,
                    "message": msg,
                    "status": "queued",
                })
                r.sent_count += 1
            r.state = "sent"


class KobSmsLog(models.Model):
    _name = "kob.sms.log"
    _description = "SMS Delivery Log"
    _order = "create_date desc"

    blast_id = fields.Many2one("kob.sms.blast", ondelete="cascade")
    partner_id = fields.Many2one("res.partner")
    phone = fields.Char()
    message = fields.Text()
    status = fields.Selection(
        [("queued", "Queued"), ("sent", "Sent"),
         ("delivered", "Delivered"), ("failed", "Failed")],
        default="queued",
    )
    provider_msg_id = fields.Char()
    error_message = fields.Char()
    cost = fields.Float()
