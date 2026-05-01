# -*- coding: utf-8 -*-
"""Volume rebate — group-level vendor rebate by spend tier."""

from odoo import api, fields, models, _


class KobVolumeRebateTier(models.Model):
    _name = "kob.volume.rebate.tier"
    _description = "Volume Rebate Tier"
    _order = "vendor_id, threshold_min"

    vendor_id = fields.Many2one(
        "res.partner", required=True, domain=[("supplier_rank", ">", 0)],
    )
    threshold_min = fields.Float(digits=(18, 2))
    threshold_max = fields.Float(digits=(18, 2), help="0 = no max")
    rebate_pct = fields.Float(digits=(6, 4), required=True)
    period_kind = fields.Selection(
        [("monthly", "Monthly"), ("quarterly", "Quarterly"), ("annual", "Annual")],
        default="quarterly",
    )
    active = fields.Boolean(default=True)
    note = fields.Char()


class KobVolumeRebateAccrual(models.Model):
    _name = "kob.volume.rebate.accrual"
    _description = "Volume Rebate Accrual"
    _order = "period_start desc, vendor_id"
    _sql_constraints = [
        (
            "uniq_vendor_period",
            "unique(vendor_id, period_kind, period_start)",
            "Accrual already exists for this vendor/period.",
        ),
    ]

    vendor_id = fields.Many2one("res.partner", required=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    period_kind = fields.Selection(
        [("monthly", "Monthly"), ("quarterly", "Quarterly"), ("annual", "Annual")],
        required=True,
    )
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    total_group_spend = fields.Monetary(currency_field="currency_id")
    matched_tier_id = fields.Many2one("kob.volume.rebate.tier")
    rebate_pct = fields.Float(digits=(6, 4))
    rebate_amount = fields.Monetary(currency_field="currency_id")
    accrued_at = fields.Datetime(default=fields.Datetime.now)

    @api.model
    def accrue(self, vendor, period_kind, period_start, period_end,
               total_group_spend):
        """Match best tier and persist an accrual snapshot."""
        Tier = self.env["kob.volume.rebate.tier"]
        tiers = Tier.search([
            ("vendor_id", "=", vendor.id),
            ("active", "=", True),
            ("period_kind", "=", period_kind),
            ("threshold_min", "<=", total_group_spend),
        ], order="threshold_min desc")
        matched = None
        for t in tiers:
            if t.threshold_max and total_group_spend > t.threshold_max:
                continue
            matched = t
            break
        rebate_pct = float(matched.rebate_pct) if matched else 0.0
        rebate_amount = round(total_group_spend * rebate_pct / 100.0, 2)
        existing = self.search([
            ("vendor_id", "=", vendor.id),
            ("period_kind", "=", period_kind),
            ("period_start", "=", period_start),
        ], limit=1)
        vals = {
            "vendor_id": vendor.id,
            "period_kind": period_kind,
            "period_start": period_start,
            "period_end": period_end,
            "total_group_spend": total_group_spend,
            "matched_tier_id": matched.id if matched else False,
            "rebate_pct": rebate_pct,
            "rebate_amount": rebate_amount,
            "accrued_at": fields.Datetime.now(),
        }
        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)
