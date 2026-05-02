# -*- coding: utf-8 -*-
"""Phase 51 — Email campaign builder + segmentation."""
from odoo import api, fields, models, _


class KobEmailCampaign(models.Model):
    _name = "kob.email.campaign"
    _description = "Email Campaign"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    subject = fields.Char(required=True)
    from_name = fields.Char(default="KOB")
    from_email = fields.Char(required=True)
    body_html = fields.Html(sanitize=False)
    state = fields.Selection(
        [("draft", "Draft"),
         ("scheduled", "Scheduled"),
         ("sending", "Sending"),
         ("sent", "Sent"),
         ("paused", "Paused"),
         ("cancelled", "Cancelled")],
        default="draft", tracking=True,
    )
    segment_id = fields.Many2one("kob.customer.segment", required=True)
    scheduled_at = fields.Datetime()
    sent_count = fields.Integer(readonly=True, default=0)
    open_count = fields.Integer(readonly=True, default=0)
    click_count = fields.Integer(readonly=True, default=0)
    unsubscribe_count = fields.Integer(readonly=True, default=0)
    bounce_count = fields.Integer(readonly=True, default=0)
    open_rate = fields.Float(compute="_compute_rates", store=False)
    click_rate = fields.Float(compute="_compute_rates", store=False)
    ab_test = fields.Boolean(string="A/B Test")
    ab_variant_b_subject = fields.Char(string="Variant B Subject")
    ab_variant_b_body = fields.Html(string="Variant B Body", sanitize=False)
    ab_split_pct = fields.Float(string="% on Variant A", default=50.0)

    @api.depends("sent_count", "open_count", "click_count")
    def _compute_rates(self):
        for r in self:
            r.open_rate = (100.0 * r.open_count / r.sent_count
                           if r.sent_count else 0)
            r.click_rate = (100.0 * r.click_count / r.sent_count
                            if r.sent_count else 0)

    def action_schedule(self):
        for r in self:
            if not r.scheduled_at:
                raise self.env["ir.exceptions"].UserError(
                    _("Set a scheduled time first."))
            r.state = "scheduled"

    def action_send_now(self):
        for r in self:
            r._render_and_send()

    def _render_and_send(self):
        self.ensure_one()
        partners = self.segment_id.compute_partners()
        Mail = self.env["mail.mail"].sudo()
        for p in partners:
            if not p.email:
                continue
            # A/B split
            use_b = self.ab_test and (hash(p.id) % 100) >= self.ab_split_pct
            subj = self.ab_variant_b_subject if use_b else self.subject
            body = self.ab_variant_b_body if use_b else self.body_html
            Mail.create({
                "subject": subj or self.subject,
                "body_html": body or self.body_html,
                "email_from": f"{self.from_name} <{self.from_email}>",
                "email_to": p.email,
            }).send()
            self.sent_count += 1
        self.state = "sent"


class KobCustomerSegment(models.Model):
    _name = "kob.customer.segment"
    _description = "Customer Segment"
    _order = "name"

    name = fields.Char(required=True)
    description = fields.Text()
    domain = fields.Char(default="[]",
                         help="Odoo domain on res.partner")
    static_partner_ids = fields.Many2many("res.partner")
    use_domain = fields.Boolean(default=True)
    member_count = fields.Integer(compute="_compute_count", store=False)

    def _compute_count(self):
        for r in self:
            r.member_count = len(r.compute_partners())

    def compute_partners(self):
        self.ensure_one()
        if self.use_domain:
            try:
                domain = eval(self.domain or "[]")  # nosec
            except Exception:
                domain = []
            return self.env["res.partner"].search(domain)
        return self.static_partner_ids
