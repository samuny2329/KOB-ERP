# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MeaCalculatorWizard(models.TransientModel):
    _name = "mea.calculator.wizard"
    _description = "MEA What-If Calculator"

    tariff_id = fields.Many2one("mea.tariff", required=True)
    is_tou = fields.Boolean(related="tariff_id.is_tou")
    billing_date = fields.Date(default=fields.Date.context_today, required=True)
    ft_period_id = fields.Many2one(
        "mea.ft.period",
        compute="_compute_ft",
        store=False,
    )
    ft_rate_satang = fields.Float(related="ft_period_id.ft_rate", readonly=True)

    kwh_total = fields.Float(string="Total kWh", digits=(12, 2))
    kwh_on_peak = fields.Float(string="On-Peak kWh", digits=(12, 2))
    kwh_off_peak = fields.Float(string="Off-Peak kWh", digits=(12, 2))
    demand_kw = fields.Float(
        string="Peak Demand (kW)",
        digits=(8, 2),
        help="Highest 15-min on-peak demand. Required for TOU tariffs to "
             "include demand charge in the estimate.",
    )

    energy_charge = fields.Float(readonly=True, digits=(12, 2))
    demand_charge_amount = fields.Float(readonly=True, digits=(12, 2))
    service_charge = fields.Float(readonly=True, digits=(12, 2))
    ft_amount = fields.Float(readonly=True, digits=(12, 2))
    subtotal = fields.Float(readonly=True, digits=(12, 2))
    vat_amount = fields.Float(readonly=True, digits=(12, 2))
    total_amount = fields.Float(string="Total (THB)", readonly=True, digits=(12, 2))

    @api.depends("billing_date")
    def _compute_ft(self):
        for w in self:
            w.ft_period_id = self.env["mea.ft.period"].get_for_date(w.billing_date)

    def action_calculate(self):
        self.ensure_one()
        # Use a synthetic "meter-like" object — calculator only needs tariff_id.
        meter_proxy = self.env["mea.meter"].new({"tariff_id": self.tariff_id.id})
        result = self.env["mea.calculator"]._compute_expected(
            meter_proxy,
            self.billing_date,
            {
                "total": self.kwh_total,
                "on_peak": self.kwh_on_peak,
                "off_peak": self.kwh_off_peak,
                "demand_kw": self.demand_kw,
            },
        )
        self.write({
            "energy_charge": result["energy"],
            "demand_charge_amount": result["demand"],
            "service_charge": result["service"],
            "ft_amount": result["ft"],
            "subtotal": result["subtotal"],
            "vat_amount": result["vat"],
            "total_amount": result["total"],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "mea.calculator.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
