# -*- coding: utf-8 -*-
"""Phase 53 — Coupon / promo engine + A/B test framework."""
import secrets
import string

from odoo import api, fields, models, _


class KobCouponProgram(models.Model):
    _name = "kob.coupon.program"
    _description = "Coupon Program"
    _order = "create_date desc"

    name = fields.Char(required=True)
    code_prefix = fields.Char(default="KOB", help="Prefix for generated codes")
    discount_type = fields.Selection(
        [("percent", "% Off"),
         ("fixed", "Fixed THB Off"),
         ("free_shipping", "Free Shipping"),
         ("bogo", "Buy One Get One")],
        required=True, default="percent",
    )
    discount_value = fields.Float()
    min_order_value = fields.Float(default=0)
    max_uses = fields.Integer(default=1, help="Max uses per coupon")
    max_uses_per_customer = fields.Integer(default=1)
    valid_from = fields.Date()
    valid_to = fields.Date()
    applicable_product_ids = fields.Many2many("product.product")
    applicable_category_ids = fields.Many2many("product.category")
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"),
         ("paused", "Paused"), ("expired", "Expired")],
        default="draft",
    )
    coupon_count = fields.Integer(compute="_compute_counts", store=False)
    redeemed_count = fields.Integer(compute="_compute_counts", store=False)
    coupon_ids = fields.One2many("kob.coupon", "program_id")

    @api.depends("coupon_ids", "coupon_ids.state")
    def _compute_counts(self):
        for r in self:
            r.coupon_count = len(r.coupon_ids)
            r.redeemed_count = len(r.coupon_ids.filtered(
                lambda c: c.state == "redeemed"))

    def action_activate(self):
        self.write({"state": "active"})

    def action_generate_codes(self):
        """Wizard call: generate N codes."""
        ctx = self.env.context or {}
        n = ctx.get("count", 100)
        Coupon = self.env["kob.coupon"]
        for r in self:
            for _ in range(n):
                Coupon.create({
                    "program_id": r.id,
                    "code": r._gen_code(),
                })
        return True

    def _gen_code(self):
        alphabet = string.ascii_uppercase + string.digits
        random_part = "".join(secrets.choice(alphabet) for _ in range(8))
        return f"{self.code_prefix}-{random_part}"


class KobCoupon(models.Model):
    _name = "kob.coupon"
    _description = "Coupon"
    _order = "create_date desc"

    program_id = fields.Many2one("kob.coupon.program", required=True,
                                 ondelete="cascade")
    code = fields.Char(required=True, index=True)
    state = fields.Selection(
        [("active", "Active"),
         ("redeemed", "Redeemed"),
         ("expired", "Expired"),
         ("voided", "Voided")],
        default="active",
    )
    used_by_partner_id = fields.Many2one("res.partner")
    used_at = fields.Datetime()
    used_on_order_id = fields.Many2one("sale.order")
    discount_applied = fields.Float()

    _sql_constraints = [
        ("kob_coupon_code_unique", "unique(code)", "Coupon code must be unique."),
    ]

    def redeem(self, partner, order, amount):
        """Mark coupon as redeemed and record discount."""
        for r in self:
            if r.state != "active":
                raise self.env["ir.exceptions"].UserError(
                    _("Coupon %s is not active.") % r.code)
            r.write({
                "state": "redeemed",
                "used_by_partner_id": partner.id,
                "used_at": fields.Datetime.now(),
                "used_on_order_id": order.id,
                "discount_applied": amount,
            })


class KobAbTest(models.Model):
    _name = "kob.ab.test"
    _description = "A/B Test"
    _order = "create_date desc"

    name = fields.Char(required=True)
    hypothesis = fields.Text(required=True)
    variant_a_label = fields.Char(default="Control")
    variant_b_label = fields.Char(default="Treatment")
    target_metric = fields.Selection(
        [("conversion_rate", "Conversion Rate"),
         ("aov", "Avg Order Value"),
         ("ctr", "Click-Through Rate"),
         ("retention", "Retention"),
         ("custom", "Custom")],
        required=True, default="conversion_rate",
    )
    start_date = fields.Date()
    end_date = fields.Date()
    sample_size_target = fields.Integer(default=1000)
    state = fields.Selection(
        [("draft", "Draft"), ("running", "Running"),
         ("complete", "Complete"), ("inconclusive", "Inconclusive")],
        default="draft",
    )
    a_sample_count = fields.Integer(default=0)
    a_conversion_count = fields.Integer(default=0)
    b_sample_count = fields.Integer(default=0)
    b_conversion_count = fields.Integer(default=0)
    a_rate = fields.Float(compute="_compute_rates", store=False)
    b_rate = fields.Float(compute="_compute_rates", store=False)
    lift_pct = fields.Float(compute="_compute_rates", store=False)
    winner = fields.Char(compute="_compute_rates", store=False)

    @api.depends("a_sample_count", "a_conversion_count",
                 "b_sample_count", "b_conversion_count")
    def _compute_rates(self):
        for r in self:
            r.a_rate = (100.0 * r.a_conversion_count / r.a_sample_count
                        if r.a_sample_count else 0)
            r.b_rate = (100.0 * r.b_conversion_count / r.b_sample_count
                        if r.b_sample_count else 0)
            r.lift_pct = ((r.b_rate - r.a_rate) / r.a_rate * 100
                          if r.a_rate else 0)
            if abs(r.lift_pct) < 5:
                r.winner = "Inconclusive"
            elif r.b_rate > r.a_rate:
                r.winner = "B"
            else:
                r.winner = "A"
