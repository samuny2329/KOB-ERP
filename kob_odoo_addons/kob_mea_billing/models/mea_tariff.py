# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MeaTariff(models.Model):
    _name = "mea.tariff"
    _description = "MEA Electricity Tariff"
    _order = "code"

    code = fields.Char(
        required=True, index=True,
        help="MEA tariff code (e.g. '3.2.3', '2.1.2'). "
             "First digit = customer type, second = voltage level, third = scheme variant.",
    )
    name = fields.Char(
        required=True, translate=True,
        help="Human-readable label shown in dropdowns.",
    )
    is_tou = fields.Boolean(
        string="Time-of-Use",
        help="True for TOU tariffs (3.x.x). TOU charges different rates for "
             "on-peak (Mon-Fri 09:00-22:00) and off-peak hours, plus a separate "
             "demand charge for peak kW. False = Flat tariff (1.x.x / 2.x.x).",
    )
    voltage_level = fields.Selection(
        [("low", "Low (< 12 kV)"), ("medium", "Medium (12-24 kV)"), ("high", "High (> 69 kV)")],
        default="medium",
        help="Voltage class. Higher voltage = lower rates (less line loss).",
    )
    peak_rate = fields.Float(
        string="Peak Rate (THB/kWh)", digits=(8, 4),
        help="On-peak energy rate (TOU only). Applied to kwh_on_peak.",
    )
    off_peak_rate = fields.Float(
        string="Off-Peak Rate (THB/kWh)", digits=(8, 4),
        help="Off-peak energy rate (TOU only). Applied to kwh_off_peak.",
    )
    flat_rate = fields.Float(
        string="Flat Rate (THB/kWh)", digits=(8, 4),
        help="Single-rate fallback (Flat tariffs without progressive tiers). "
             "If 'Progressive Tiers' below has rows, this field is ignored "
             "and rates from the tier table are used instead.",
    )
    service_charge = fields.Float(
        string="Service Charge (THB/month)", digits=(8, 2),
        help="Fixed monthly fee charged regardless of consumption "
             "(312.24 for TOU 3.2.3; 33.29 for Flat 2.1.2).",
    )
    demand_charge = fields.Float(
        string="Demand Charge (THB/kW)", digits=(8, 2),
        help="Charge per kW of highest 15-min on-peak demand (TOU only). "
             "210 THB/kW for tariff 3.2.3.",
    )
    effective_date = fields.Date(default=fields.Date.context_today)
    tier_ids = fields.One2many("mea.tariff.tier", "tariff_id", string="Progressive Tiers")
    note = fields.Text()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("uniq_code", "unique(code)", "Tariff code must be unique."),
    ]

    def name_get(self):
        return [(t.id, f"{t.code} – {t.name}") for t in self]


class MeaTariffTier(models.Model):
    _name = "mea.tariff.tier"
    _description = "MEA Tariff Progressive Tier"
    _order = "tariff_id, kwh_from"

    tariff_id = fields.Many2one("mea.tariff", required=True, ondelete="cascade")
    kwh_from = fields.Integer(string="From kWh", required=True)
    kwh_to = fields.Integer(
        string="To kWh",
        help="0 means open-ended (applies to all kWh above kwh_from).",
    )
    rate = fields.Float(string="Rate (THB/kWh)", digits=(8, 4), required=True)
    note = fields.Char()

    @api.constrains("kwh_from", "kwh_to")
    def _check_tier_range(self):
        for r in self:
            if r.kwh_to and r.kwh_to <= r.kwh_from:
                raise ValidationError(
                    "Tier 'To kWh' must be greater than 'From kWh' (or 0 for open-ended)."
                )
