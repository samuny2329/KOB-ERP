from odoo import models


class KobApprovalStep(models.Model):
    _name = "kob.approval.step"
    _inherit = ["kob.approval.step", "kob.stage.tracker.mixin"]

    _stage_field = "state"
    _stage_terminal = ("approved", "rejected")
    _stage_track_on_create = True
