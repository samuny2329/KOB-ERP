"""WMS Multi-Order Pick Group.

A pick group bundles multiple ``wms.sales.order`` records that share the same
physical picking sheet (e.g. printed by Print_Label-App with identical
``sku_sort``).  Status promotion to ``picked``/``packed`` is gated until
ALL member orders complete — preventing the bug where one SO advances to
Picked while siblings remain at 0/N.

Sources:
    print_label_app  — imported from Print_Label-App Excel export
                       (column ``running="No.{set}-{pos}/{total}"``)
    auto_basket      — created on-the-fly by ``queue_scan_dispatch`` when
                       multiple SOs are scanned together without a pre-existing
                       group
    manual           — created by user in the back-office
"""
from odoo import api, fields, models


class WmsPickGroup(models.Model):
    _name = "wms.pick.group"
    _description = "WMS Multi-Order Pick Group"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        required=True, index=True, tracking=True,
        help="Set key — e.g. lead order_sn '260504GTHSE7DX' or "
             "sku_sort hash from Print_Label-App.",
    )
    sku_sort = fields.Char(
        index=True,
        help="Concatenated SKU+qty key from Print_Label-App grouping "
             "(e.g. 'KHKB038^1+KTSD088^1'). Same value across all members.",
    )
    source = fields.Selection(
        [
            ("print_label_app", "Print_Label-App import"),
            ("auto_basket", "Auto from picking basket"),
            ("manual", "Manual"),
        ],
        default="manual",
        required=True,
        tracking=True,
    )

    order_ids = fields.One2many(
        "wms.sales.order", "pick_group_id", string="Orders")
    order_count = fields.Integer(
        compute="_compute_counts", store=True)
    expected_total = fields.Integer(
        compute="_compute_counts", store=True,
        help="Sum of expected_total across all member orders (qty target).",
    )
    picked_total = fields.Integer(
        compute="_compute_counts", store=True)
    packed_total = fields.Integer(
        compute="_compute_counts", store=True)
    pick_progress = fields.Float(
        compute="_compute_counts", store=True,
        help="picked_total / expected_total × 100 (0–100).",
    )

    group_picked = fields.Boolean(
        compute="_compute_completion", store=True,
        help="True only when ALL active member orders have all_picked=True. "
             "Cancelled members are ignored. Empty group = False.",
    )
    group_packed = fields.Boolean(
        compute="_compute_completion", store=True)

    state = fields.Selection(
        [
            ("open", "Open"),
            ("picking", "Picking"),
            ("picked", "Picked"),
            ("packing", "Packing"),
            ("packed", "Packed"),
            ("shipped", "Shipped"),
            ("cancelled", "Cancelled"),
        ],
        default="open",
        tracking=True,
        index=True,
    )

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company)

    note = fields.Text()

    @api.depends("order_ids.expected_total", "order_ids.picked_total",
                 "order_ids.packed_total", "order_ids.status", "order_ids")
    def _compute_counts(self):
        for grp in self:
            active = grp.order_ids.filtered(lambda o: o.status != "cancelled")
            grp.order_count = len(active)
            grp.expected_total = sum(active.mapped("expected_total"))
            grp.picked_total = sum(active.mapped("picked_total"))
            grp.packed_total = sum(active.mapped("packed_total"))
            grp.pick_progress = (
                100.0 * grp.picked_total / grp.expected_total
                if grp.expected_total else 0.0
            )

    @api.depends("order_ids.all_picked", "order_ids.all_packed",
                 "order_ids.status", "order_ids")
    def _compute_completion(self):
        for grp in self:
            active = grp.order_ids.filtered(lambda o: o.status != "cancelled")
            grp.group_picked = bool(active) and all(
                o.all_picked for o in active)
            grp.group_packed = bool(active) and all(
                o.all_packed for o in active)

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Orders in Group",
            "res_model": "wms.sales.order",
            "view_mode": "list,form",
            "domain": [("pick_group_id", "=", self.id)],
            "context": {"default_pick_group_id": self.id},
        }
