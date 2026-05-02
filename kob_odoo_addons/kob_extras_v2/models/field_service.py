# -*- coding: utf-8 -*-
"""Phase 31 — Field Service technician dispatch (minimal)."""
from odoo import api, fields, models


class KobFieldServiceTask(models.Model):
    _name = "kob.field.service.task"
    _description = "Field Service Task"
    _inherit = ["mail.thread"]
    _order = "schedule_date"

    name = fields.Char(required=True)
    customer_id = fields.Many2one("res.partner", required=True)
    address = fields.Char()
    technician_id = fields.Many2one("res.users", string="Technician")
    schedule_date = fields.Datetime(required=True)
    duration_hours = fields.Float(default=2.0)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft", tracking=True,
    )
    description = fields.Text()
    completion_notes = fields.Text()
    related_so = fields.Many2one("sale.order", string="Related SO")
    related_invoice = fields.Many2one("account.move", string="Invoice")

    def action_schedule(self):
        for r in self:
            r.state = "scheduled"

    def action_start(self):
        for r in self:
            r.state = "in_progress"

    def action_complete(self):
        for r in self:
            r.state = "done"
