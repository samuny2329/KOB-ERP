# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MeaMeter(models.Model):
    _name = "mea.meter"
    _description = "MEA Electricity Meter"
    _order = "site_short, ca_number"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        compute="_compute_name", store=True,
        help="Auto-computed display name: [CA] Site Code.",
    )
    ca_number = fields.Char(
        string="CA Number (บัญชีแสดงสัญญา)",
        required=True,
        index=True,
        size=9,
        tracking=True,
        help="9-digit Contract Account number from MEA bill (Ref No.1). "
             "Identifies the account holder; one site can have its CA reassigned "
             "when ownership transfers (e.g. ULVAC → KOB for KK16 in Feb 2026).",
    )
    meter_id = fields.Char(
        string="Meter ID (รหัสเครื่องวัด)",
        required=True,
        index=True,
        size=8,
        tracking=True,
        help="8-digit physical meter device identifier (Installation No. on bill). "
             "Stays constant even if CA Number changes — use this to track "
             "consumption history across ownership transfers.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_name = fields.Char(
        string="Owner Name",
        help="Company name as printed on the MEA bill.",
    )
    site_short = fields.Char(
        string="Site Code",
        required=True,
        help="Short identifier shown across the UI (e.g. 'KOB-HQ', 'BTV-110/3'). "
             "Keep under 16 chars — used in lists, charts, and KPI cards.",
    )
    site_address = fields.Text(
        string="Site Address",
        help="Full Thai postal address as printed on the MEA bill.",
    )
    district = fields.Char(
        string="MEA District",
        help="Name of the MEA service district (e.g. 'บางพลี', 'บางกะปิ'). "
             "Useful for routing on-site service calls.",
    )
    tariff_id = fields.Many2one(
        "mea.tariff", required=True, tracking=True,
        help="Tariff plan applied by MEA (e.g. 3.2.3 TOU, 2.1.2 Flat). "
             "Drives Energy Charge calculation: TOU uses peak/off-peak split, "
             "Flat uses progressive tier rates.",
    )
    is_tou = fields.Boolean(
        related="tariff_id.is_tou", store=True,
        help="True when tariff is Time-of-Use (3.x.x). Determines whether On/Off "
             "Peak split + Demand kW columns are applicable.",
    )
    bill_history_ids = fields.One2many("mea.bill.history", "meter_id")
    asset_ids = fields.One2many("mea.asset", "meter_id")
    asset_count = fields.Integer(compute="_compute_asset_stats")
    asset_total_kwh_month = fields.Float(
        compute="_compute_asset_stats", digits=(12, 2),
        help="Sum of kwh_per_month across all active assets at this site.",
    )
    asset_total_kw = fields.Integer(
        compute="_compute_asset_stats",
        help="Sum of total_rating_w (instantaneous max load) — should "
             "approximate the meter's peak demand_on_peak.",
    )
    bill_count = fields.Integer(
        compute="_compute_bill_stats",
        help="Total number of monthly bill records linked to this meter.",
    )
    last_bill_date = fields.Date(
        compute="_compute_bill_stats", store=True,
        help="Billing month of the most recent recorded bill.",
    )
    last_reading_kwh = fields.Float(
        compute="_compute_bill_stats", store=True, digits=(12, 2),
        help="kWh consumed in the most recent billing period.",
    )
    last_total_amount = fields.Float(
        compute="_compute_bill_stats", store=True, digits=(12, 2),
        help="Total THB billed for the most recent period (incl. VAT 7%).",
    )
    state = fields.Selection(
        [("active", "Active"), ("inactive", "Inactive")],
        default="active",
        tracking=True,
    )
    note = fields.Text()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("uniq_ca_number", "unique(ca_number)", "CA Number must be unique."),
    ]

    @api.depends("ca_number", "site_short")
    def _compute_name(self):
        for r in self:
            r.name = f"[{r.ca_number or '?'}] {r.site_short or ''}".strip()

    @api.depends("asset_ids", "asset_ids.kwh_per_month", "asset_ids.total_rating_w",
                 "asset_ids.state")
    def _compute_asset_stats(self):
        for r in self:
            active = r.asset_ids.filtered(lambda a: a.state == "active")
            r.asset_count = len(active)
            r.asset_total_kwh_month = sum(active.mapped("kwh_per_month"))
            r.asset_total_kw = sum(active.mapped("total_rating_w")) // 1000

    @api.depends("bill_history_ids.billing_month", "bill_history_ids.kwh_total",
                 "bill_history_ids.total_amount")
    def _compute_bill_stats(self):
        for r in self:
            r.bill_count = len(r.bill_history_ids)
            latest = r.bill_history_ids.sorted("billing_month", reverse=True)[:1]
            r.last_bill_date = latest.billing_month if latest else False
            r.last_reading_kwh = latest.kwh_total if latest else 0.0
            r.last_total_amount = latest.total_amount if latest else 0.0

    @api.constrains("ca_number")
    def _check_ca_format(self):
        for r in self:
            if r.ca_number and not re.fullmatch(r"\d{9}", r.ca_number):
                raise ValidationError("CA Number must be exactly 9 digits.")

    @api.constrains("meter_id")
    def _check_meter_format(self):
        for r in self:
            if r.meter_id and not re.fullmatch(r"\d{6,10}", r.meter_id):
                raise ValidationError("Meter ID must be 6-10 digits.")

    def action_view_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Bills – {self.site_short}",
            "res_model": "mea.bill.history",
            "view_mode": "list,form",
            "domain": [("meter_id", "=", self.id)],
            "context": {"default_meter_id": self.id},
        }

    def action_meter_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "kob_mea_meter_dashboard",
            "name": f"Dashboard – {self.site_short}",
            "context": {"default_meter_id": self.id, "active_id": self.id},
        }

    def action_view_assets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Assets – {self.site_short}",
            "res_model": "mea.asset",
            "view_mode": "list,form,kanban",
            "domain": [("meter_id", "=", self.id)],
            "context": {"default_meter_id": self.id},
        }
