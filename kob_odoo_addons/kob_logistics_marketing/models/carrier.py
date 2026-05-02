# -*- coding: utf-8 -*-
"""Phase 48 — Multi-carrier shipping rate shopping.

Maintains a list of supported Thai carriers (DHL, Kerry, Flash, J&T, Ninja,
Thailand Post) with per-carrier rate cards. Provides rate-shop API:
given (origin postal-code, dest postal-code, weight kg, dimensions cm)
return ranked carrier offers.
"""
from odoo import api, fields, models


class KobShippingCarrier(models.Model):
    _name = "kob.shipping.carrier"
    _description = "Shipping Carrier"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True,
                       help="Internal code: dhl, kerry, flash, jt, ninja, thp")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    api_key = fields.Char()
    api_secret = fields.Char()
    api_endpoint = fields.Char()
    is_test_mode = fields.Boolean(default=True)
    supports_cod = fields.Boolean(string="Supports COD", default=True)
    supports_pickup = fields.Boolean(default=True)
    supports_dropoff = fields.Boolean(default=True)
    average_lead_time_days = fields.Integer(default=2)
    rate_card_ids = fields.One2many("kob.shipping.rate", "carrier_id")
    notes = fields.Text()

    _sql_constraints = [
        ("kob_carrier_code_unique", "unique(code)", "Carrier code must be unique."),
    ]


class KobShippingRate(models.Model):
    _name = "kob.shipping.rate"
    _description = "Shipping Rate Card"
    _order = "carrier_id, weight_min"

    carrier_id = fields.Many2one("kob.shipping.carrier", required=True,
                                 ondelete="cascade")
    name = fields.Char(required=True, default="Standard")
    weight_min = fields.Float(string="Min Weight (kg)", default=0)
    weight_max = fields.Float(string="Max Weight (kg)", default=999)
    base_price = fields.Float(required=True)
    per_kg_above = fields.Float(default=0,
                                help="Additional charge per kg above weight_min")
    fuel_surcharge_pct = fields.Float(default=0)
    region_pattern = fields.Char(string="Postal Code Pattern",
                                 help="Regex; empty = nationwide")
    estimated_days = fields.Integer(default=2)
    cod_fee_pct = fields.Float(default=2.0,
                               help="% of COD amount as carrier fee")

    def compute_total(self, weight_kg, cod_amount=0.0):
        self.ensure_one()
        extra_kg = max(0, weight_kg - self.weight_min)
        gross = self.base_price + extra_kg * self.per_kg_above
        gross *= (1 + self.fuel_surcharge_pct / 100)
        cod_fee = cod_amount * self.cod_fee_pct / 100 if cod_amount else 0
        return round(gross + cod_fee, 2)


class KobRateShopWizard(models.TransientModel):
    _name = "kob.rate.shop.wizard"
    _description = "Shipping Rate Shop"

    origin_postal = fields.Char(string="Origin Postal Code", required=True)
    dest_postal = fields.Char(string="Destination Postal Code", required=True)
    weight_kg = fields.Float(string="Weight (kg)", required=True, default=1.0)
    cod_amount = fields.Float(string="COD Amount (THB)", default=0)
    quote_ids = fields.One2many("kob.rate.shop.quote", "wizard_id")

    def action_shop(self):
        self.ensure_one()
        self.quote_ids.unlink()
        Carrier = self.env["kob.shipping.carrier"].search([("active", "=", True)])
        Rate = self.env["kob.shipping.rate"]
        Quote = self.env["kob.rate.shop.quote"]
        rows = []
        for c in Carrier:
            rates = Rate.search([
                ("carrier_id", "=", c.id),
                ("weight_min", "<=", self.weight_kg),
                ("weight_max", ">=", self.weight_kg),
            ])
            for r in rates:
                rows.append({
                    "wizard_id": self.id,
                    "carrier_id": c.id,
                    "rate_id": r.id,
                    "service": r.name,
                    "price": r.compute_total(self.weight_kg, self.cod_amount),
                    "estimated_days": r.estimated_days,
                })
        # Sort: cheapest first
        rows.sort(key=lambda x: x["price"])
        for i, row in enumerate(rows):
            row["rank"] = i + 1
            Quote.create(row)
        return {
            "type": "ir.actions.act_window",
            "res_model": "kob.rate.shop.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class KobRateShopQuote(models.TransientModel):
    _name = "kob.rate.shop.quote"
    _description = "Rate Shop Quote"
    _order = "rank"

    wizard_id = fields.Many2one("kob.rate.shop.wizard", ondelete="cascade")
    carrier_id = fields.Many2one("kob.shipping.carrier")
    rate_id = fields.Many2one("kob.shipping.rate")
    service = fields.Char()
    price = fields.Float()
    estimated_days = fields.Integer()
    rank = fields.Integer()
