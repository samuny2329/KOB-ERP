"""Resolves a default courier for an outbound order when none is set.

Strategy (first match wins):
1. Active platform→courier mapping for the order's platform (per company)
2. Partner-level default if `default_courier_id` exists on res.partner
3. The 'PENDING' fallback courier (auto-created on install)
"""

from odoo import api, fields, models, _


PENDING_CODE = "PENDING"
PENDING_NAME = "PENDING (assign later)"


class WmsCourierPlatformMap(models.Model):
    _name = "wms.courier.platform.map"
    _description = "Platform → Default Courier mapping"
    _order = "sequence, platform"
    _rec_name = "platform"

    sequence = fields.Integer(default=10)
    platform = fields.Selection(
        [
            ("odoo", "Odoo"),
            ("shopee", "Shopee"),
            ("lazada", "Lazada"),
            ("tiktok", "TikTok"),
            ("pos", "Point of Sale"),
            ("manual", "Manual"),
        ],
        required=True,
    )
    courier_id = fields.Many2one(
        "wms.courier", required=True, ondelete="restrict",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, required=True,
    )
    note = fields.Char()

    _sql_constraints = [
        (
            "platform_company_unique",
            "unique(platform, company_id)",
            "Only one mapping per platform per company.",
        ),
    ]

    @api.model
    def resolve(self, platform, company=None):
        company = company or self.env.company
        if not platform:
            return self.env["wms.courier"]
        m = self.search([
            ("platform", "=", platform),
            ("company_id", "=", company.id),
            ("active", "=", True),
        ], limit=1)
        return m.courier_id if m else self.env["wms.courier"]


class WmsCourier(models.Model):
    _inherit = "wms.courier"

    is_pending_fallback = fields.Boolean(
        default=False,
        help="Marks this courier as the auto-created PENDING fallback. "
             "Scan items routed here need manual courier reassignment.",
    )

    @api.model
    def get_pending_fallback(self, company=None):
        """Return (creating if needed) the PENDING fallback courier for the
        given company."""
        company = company or self.env.company
        c = self.sudo().search([
            ("is_pending_fallback", "=", True),
            ("company_id", "=", company.id),
        ], limit=1)
        if c:
            return c
        # Avoid the unique(code, company_id) collision on re-create
        existing_by_code = self.sudo().search([
            ("code", "=", PENDING_CODE),
            ("company_id", "=", company.id),
        ], limit=1)
        if existing_by_code:
            existing_by_code.write({"is_pending_fallback": True})
            return existing_by_code
        return self.sudo().create({
            "name": PENDING_NAME,
            "code": PENDING_CODE,
            "is_pending_fallback": True,
            "color_hex": "#999999",
            "sequence": 999,
            "company_id": company.id,
        })


class WmsSalesOrderCourierResolver(models.Model):
    _inherit = "wms.sales.order"

    def _kob_resolve_default_courier(self):
        """Return a courier to use when self.courier_id is empty."""
        self.ensure_one()
        company = self.company_id or self.env.company

        # 1. Platform → courier mapping
        mapped = self.env["wms.courier.platform.map"].sudo().resolve(
            self.platform, company,
        )
        if mapped:
            return mapped

        # 2. Partner-level default (if such a field exists)
        partner = getattr(self, "partner_id", None)
        if partner and "default_courier_id" in partner._fields:
            if partner.default_courier_id:
                return partner.default_courier_id

        # 3. PENDING fallback
        return self.env["wms.courier"].sudo().get_pending_fallback(company)
