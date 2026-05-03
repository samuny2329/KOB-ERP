from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    stock_lite_qty = fields.Float(
        compute="_compute_stock_lite_qty",
        string="Available stock (sum across all internal locs)",
    )
    stock_lite_status = fields.Selection(
        [
            ("none", "No tracked products"),
            ("ok", "Sufficient"),
            ("partial", "Partially available"),
            ("out", "Out of stock"),
        ],
        compute="_compute_stock_lite_qty",
    )

    @api.depends("order_line.product_id", "order_line.product_uom_qty")
    def _compute_stock_lite_qty(self):
        Quant = self.env["stock.quant"]
        for so in self:
            tracked_lines = so.order_line.filtered(
                lambda l: l.product_id and l.product_id.is_storable
                if hasattr(l.product_id, "is_storable")
                else l.product_id and l.product_id.type == "product"
            )
            if not tracked_lines:
                so.stock_lite_qty = 0.0
                so.stock_lite_status = "none"
                continue
            # Aggregate available qty per line
            shortage = False
            partial = False
            total_avail = 0.0
            for line in tracked_lines:
                avail = sum(Quant.search([
                    ("product_id", "=", line.product_id.id),
                    ("location_id.usage", "=", "internal"),
                ]).mapped("available_quantity"))
                total_avail += avail
                if avail < line.product_uom_qty:
                    if avail <= 0:
                        shortage = True
                    else:
                        partial = True
            so.stock_lite_qty = total_avail
            if shortage and not partial:
                so.stock_lite_status = "out"
            elif partial or shortage:
                so.stock_lite_status = "partial"
            else:
                so.stock_lite_status = "ok"

    def action_view_stock_lite(self):
        """Open stock.quant list filtered to products on this SO."""
        self.ensure_one()
        product_ids = self.order_line.mapped("product_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock — %s") % self.name,
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "domain": [
                ("product_id", "in", product_ids),
                ("location_id.usage", "=", "internal"),
            ],
            "context": {
                "search_default_groupby_product": 1,
                "search_default_groupby_location": 0,
            },
        }

    def action_quick_deliver(self):
        """Create an outgoing stock.picking pre-filled from SO lines.
        Bypasses the full delivery wizard for fast quoting flows."""
        self.ensure_one()
        warehouse = self.warehouse_id or self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_id.id)], limit=1
        )
        if not warehouse or not warehouse.out_type_id:
            return {}
        out_pt = warehouse.out_type_id
        Picking = self.env["stock.picking"]
        moves = []
        for line in self.order_line.filtered(
            lambda l: l.product_id and (
                getattr(l.product_id, "is_storable", False) or l.product_id.type == "product"
            )
        ):
            uom_id = (
                line.product_uom_id.id
                if hasattr(line, "product_uom_id") and line.product_uom_id
                else line.product_id.uom_id.id
            )
            moves.append((0, 0, {
                "description_picking": line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": line.product_uom_qty,
                "product_uom": uom_id,
                "location_id": out_pt.default_location_src_id.id,
                "location_dest_id": out_pt.default_location_dest_id.id,
            }))
        if not moves:
            return {}
        picking = Picking.create({
            "partner_id": self.partner_id.id,
            "picking_type_id": out_pt.id,
            "location_id": out_pt.default_location_src_id.id,
            "location_dest_id": out_pt.default_location_dest_id.id,
            "origin": self.name,
            "move_ids": moves,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Quick Deliver — %s") % self.name,
            "res_model": "stock.picking",
            "res_id": picking.id,
            "view_mode": "form",
            "target": "current",
        }
