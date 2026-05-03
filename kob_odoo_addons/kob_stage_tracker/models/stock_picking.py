from odoo import models


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "kob.stage.tracker.mixin"]

    _stage_field = "state"
    _stage_terminal = ("done", "cancel")
    _stage_track_on_create = True
