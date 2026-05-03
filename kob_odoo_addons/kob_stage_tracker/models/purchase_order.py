from odoo import models


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "kob.stage.tracker.mixin"]

    _stage_field = "approval_state"
    _stage_terminal = ("approved", "rejected", "not_required")
    _stage_track_on_create = False
