# -*- coding: utf-8 -*-
"""KOB Helpdesk — minimal ticket model."""
from odoo import api, fields, models


class KobHelpdeskCategory(models.Model):
    _name = "kob.helpdesk.category"
    _description = "Helpdesk Category"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer()


class KobHelpdeskTicket(models.Model):
    _name = "kob.helpdesk.ticket"
    _description = "KOB Helpdesk Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, id desc"

    name = fields.Char(string="Subject", required=True, tracking=True)
    number = fields.Char(
        string="Ticket #", copy=False, readonly=True,
        default=lambda s: s.env["ir.sequence"].next_by_code(
            "kob.helpdesk.ticket",
        ) or "NEW",
    )
    description = fields.Html(string="Description")
    category_id = fields.Many2one("kob.helpdesk.category", string="Category")
    priority = fields.Selection(
        [("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Urgent")],
        default="1", tracking=True,
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("in_progress", "In Progress"),
            ("waiting", "Waiting Customer"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="new",
        tracking=True,
        required=True,
    )
    partner_id = fields.Many2one("res.partner", string="Customer", tracking=True)
    partner_email = fields.Char(string="Email", related="partner_id.email")
    assignee_id = fields.Many2one(
        "res.users", string="Assigned To",
        default=lambda s: s.env.user, tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )
    sale_order_id = fields.Many2one("sale.order", string="Related Sale Order")
    invoice_id = fields.Many2one("account.move", string="Related Invoice",
                                  domain="[('move_type','in',('out_invoice','out_refund'))]")
    date_open = fields.Datetime(default=fields.Datetime.now, readonly=True)
    date_resolved = fields.Datetime(readonly=True, tracking=True)
    duration_hours = fields.Float(
        compute="_compute_duration", store=True,
        help="Hours from open → resolved.",
    )
    tag_ids = fields.Many2many("res.partner.category", string="Tags")
    resolution = fields.Text(help="What was done to resolve the ticket?")

    @api.depends("date_open", "date_resolved")
    def _compute_duration(self):
        for r in self:
            if r.date_resolved and r.date_open:
                delta = r.date_resolved - r.date_open
                r.duration_hours = delta.total_seconds() / 3600.0
            else:
                r.duration_hours = 0.0

    def action_start(self):
        for r in self:
            r.state = "in_progress"

    def action_wait_customer(self):
        for r in self:
            r.state = "waiting"

    def action_resolve(self):
        for r in self:
            r.state = "resolved"
            r.date_resolved = fields.Datetime.now()

    def action_close(self):
        for r in self:
            r.state = "closed"

    def action_cancel(self):
        for r in self:
            r.state = "cancelled"
