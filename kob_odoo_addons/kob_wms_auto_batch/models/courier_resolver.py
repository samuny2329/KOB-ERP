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

    def apply_to_pending(self):
        """Walk through scan items in *any* still-scanning batch whose
        current courier no longer matches the mapping rule (including those
        parked in the PENDING fallback batch). Reassign the order courier
        and reroute the scan item into the proper (round, courier, platform)
        batch.

        Skips items in dispatched/cancelled batches — those are already
        out the door. Returns count of items moved.
        """
        ScanItem = self.env["wms.scan.item"].sudo()
        Batch = self.env["wms.courier.batch"].sudo()
        Round = self.env["wms.dispatch.round"].sudo()
        SO = self.env["wms.sales.order"].sudo()

        moved = 0
        # If called on an empty recordset, scan ALL active mappings
        mappings = self if self else self.search([("active", "=", True)])

        for mapping in mappings:
            if not mapping.active or not mapping.courier_id:
                continue
            new_courier = mapping.courier_id
            company = mapping.company_id

            # Find all scan items still in OPEN (scanning) batches for this
            # platform/company that currently sit on a courier that DOES
            # NOT match the new mapping. Captures both PENDING fallback
            # scans and previously-misrouted scans.
            misrouted_items = ScanItem.search([
                ("batch_id.state", "=", "scanning"),
                ("batch_id.company_id", "=", company.id),
                ("sales_order_id.platform", "=", mapping.platform),
                ("batch_id.courier_id", "!=", new_courier.id),
            ])

            for item in misrouted_items:
                order = item.sales_order_id
                if not order:
                    continue
                # Update order + scan item courier
                order.with_context(skip_track=True).courier_id = new_courier.id
                item.write({"courier_id": new_courier.id})

                # Reroute via the same logic action_ship uses
                old_batch = item.batch_id
                active_round = Round.get_or_create_active(company)
                target = SO._kob_pick_batch(
                    Batch, active_round, order, True,
                )
                if target.id != item.batch_id.id:
                    item.write({"batch_id": target.id})
                    moved += 1

                # Auto-cancel old batch if now empty (any courier, not just
                # PENDING — keeps the dispatch list clean).
                if old_batch and old_batch.id != target.id and not old_batch.scan_item_ids:
                    if old_batch.state == "scanning":
                        old_batch.write({"state": "cancelled"})

        return moved

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Auto-apply newly created mappings to existing PENDING items
        try:
            records.apply_to_pending()
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "apply_to_pending failed on map create"
            )
        return records

    def write(self, vals):
        res = super().write(vals)
        # Re-apply if courier or active flipped
        if any(k in vals for k in ("courier_id", "active", "platform")):
            try:
                self.apply_to_pending()
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "apply_to_pending failed on map write"
                )
        return res

    def action_reapply(self):
        """Manual button: re-run apply_to_pending on selection."""
        moved = (self if self else self.search([("active", "=", True)])).apply_to_pending()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Re-applied mapping"),
                "message": _("%s scan item(s) moved out of PENDING.") % moved,
                "type": "success",
                "sticky": False,
            },
        }


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
