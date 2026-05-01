# -*- coding: utf-8 -*-
"""Cross-company employee transfer (preserves service + leave).

Ported from ``backend/modules/hr/models_advanced.py``
(``EmployeeTransfer``).

Business case (real KOB workflow):
  An employee moves from บริษัท คิสออฟบิวตี้ จำกัด (KOB) to บริษัท
  บิวตี้วิลล์ จำกัด (BTV).  We do **not** terminate + rehire — that
  would reset Thai-LPA tenure (and SSO seniority).  Instead, we keep
  the same ``hr.employee`` record and rewrite ``company_id`` /
  ``department_id``, optionally also reassigning the worker's
  warehouse for WMS PIN access.

State machine:
  pending → approved → completed   (terminal)
                    ↘ cancelled    (terminal)
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobEmployeeTransfer(models.Model):
    _name = "kob.employee.transfer"
    _description = "Inter-Company Employee Transfer"
    _order = "effective_date desc"

    name = fields.Char(
        string="Reference",
        compute="_compute_name", store=True,
    )
    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="cascade", index=True,
        tracking=True,
    )
    from_company_id = fields.Many2one(
        "res.company", string="From Company", required=True,
        default=lambda s: s.env.company,
    )
    to_company_id = fields.Many2one(
        "res.company", string="To Company", required=True,
    )
    effective_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True,
    )
    new_position = fields.Char()
    new_department_id = fields.Many2one("hr.department", string="New Dept.")
    salary_adjustment_pct = fields.Float(
        digits=(6, 4), default=0,
        help="0.05 = +5% on transfer.",
    )
    keep_service_date = fields.Boolean(
        default=True,
        help="Preserve original join date so Thai LPA tenure is unbroken.",
    )
    keep_leave_balance = fields.Boolean(default=True)
    reason = fields.Text()
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        tracking=True,
    )
    completed_at = fields.Datetime(readonly=True)

    @api.depends("employee_id", "from_company_id", "to_company_id", "effective_date")
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.from_company_id and rec.to_company_id:
                rec.name = "%s: %s → %s (%s)" % (
                    rec.employee_id.name,
                    rec.from_company_id.name,
                    rec.to_company_id.name,
                    rec.effective_date or "",
                )
            else:
                rec.name = _("Draft Transfer")

    @api.constrains("from_company_id", "to_company_id")
    def _check_companies(self):
        for rec in self:
            if rec.from_company_id == rec.to_company_id:
                raise UserError(
                    _("Source and destination companies must differ."),
                )

    def action_approve(self):
        for rec in self:
            if rec.state != "pending":
                raise UserError(_("Only pending transfers can be approved."))
            rec.state = "approved"

    def action_complete(self):
        """Apply the transfer: rewrite employee.company_id + dept."""
        for rec in self:
            if rec.state != "approved":
                raise UserError(_("Approve the transfer before completing."))
            emp = rec.employee_id
            vals = {"company_id": rec.to_company_id.id}
            if rec.new_department_id:
                vals["department_id"] = rec.new_department_id.id
            if rec.new_position:
                vals["job_title"] = rec.new_position
            emp.write(vals)
            rec.write({
                "state": "completed",
                "completed_at": fields.Datetime.now(),
            })

    def action_cancel(self):
        for rec in self:
            if rec.state in ("completed",):
                raise UserError(_("Cannot cancel a completed transfer."))
            rec.state = "cancelled"
