"""Smart-button inheritance — link PO/MO/Picking back to thiti.plan.run."""
from odoo import _, api, fields, models


class PurchaseOrderThitiLink(models.Model):
    _inherit = "purchase.order"

    thiti_replenishment_ids = fields.One2many(
        "thiti.plan.replenishment", "purchase_order_id",
        string="Thiti Replenishments",
    )
    thiti_run_id = fields.Many2one(
        "thiti.plan.run", compute="_compute_thiti_run", store=True, index=True,
    )

    @api.depends("thiti_replenishment_ids")
    def _compute_thiti_run(self):
        for po in self:
            po.thiti_run_id = po.thiti_replenishment_ids[:1].run_id


class MrpProductionThitiLink(models.Model):
    _inherit = "mrp.production"

    thiti_replenishment_ids = fields.One2many(
        "thiti.plan.replenishment", "production_id",
        string="Thiti Replenishments",
    )
    thiti_run_id = fields.Many2one(
        "thiti.plan.run", compute="_compute_thiti_run", store=True, index=True,
    )

    @api.depends("thiti_replenishment_ids")
    def _compute_thiti_run(self):
        for mo in self:
            mo.thiti_run_id = mo.thiti_replenishment_ids[:1].run_id


class StockPickingThitiLink(models.Model):
    _inherit = "stock.picking"

    thiti_replenishment_ids = fields.One2many(
        "thiti.plan.replenishment", "picking_id",
        string="Thiti Replenishments",
    )
    thiti_run_id = fields.Many2one(
        "thiti.plan.run", compute="_compute_thiti_run", store=True, index=True,
    )

    @api.depends("thiti_replenishment_ids")
    def _compute_thiti_run(self):
        for pk in self:
            pk.thiti_run_id = pk.thiti_replenishment_ids[:1].run_id
