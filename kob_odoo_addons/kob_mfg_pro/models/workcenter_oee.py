# -*- coding: utf-8 -*-
"""Per-shift OEE snapshot for a work-centre.

OEE = Availability × Performance × Quality (each 0..1, multiplied to 0..1
then percent).
"""

from odoo import api, fields, models


class MfgWorkcenterOee(models.Model):
    _name = "mfg.workcenter.oee"
    _description = "Work-Centre OEE Snapshot"
    _order = "oee_date desc, workcenter_id"
    _sql_constraints = [
        (
            "uniq_wc_date_shift",
            "unique(workcenter_id, oee_date, shift_id)",
            "OEE snapshot already exists for this work-centre/date/shift.",
        ),
    ]

    workcenter_id = fields.Many2one(
        "mrp.workcenter", required=True, ondelete="cascade", index=True,
    )
    shift_id = fields.Many2one(
        "mfg.production.shift", ondelete="set null",
    )
    oee_date = fields.Date(required=True, default=fields.Date.context_today)
    planned_time = fields.Integer(help="Minutes scheduled.")
    available_time = fields.Integer(help="Minutes machine actually ran.")
    run_time = fields.Integer(help="Minutes producing parts.")
    ideal_cycle_time = fields.Float(
        digits=(8, 4),
        help="Ideal minutes per unit.",
    )
    total_units = fields.Integer()
    good_units = fields.Integer()
    availability = fields.Float(
        digits=(5, 2), compute="_compute_oee", store=True,
    )
    performance = fields.Float(
        digits=(5, 2), compute="_compute_oee", store=True,
    )
    quality = fields.Float(
        digits=(5, 2), compute="_compute_oee", store=True,
    )
    oee = fields.Float(
        digits=(5, 2), compute="_compute_oee", store=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )

    @api.depends(
        "planned_time", "available_time", "run_time",
        "ideal_cycle_time", "total_units", "good_units",
    )
    def _compute_oee(self):
        for rec in self:
            avail = (
                (rec.available_time / rec.planned_time) * 100.0
                if rec.planned_time else 0.0
            )
            perf = 0.0
            if rec.run_time and rec.ideal_cycle_time and rec.total_units:
                perf = min(
                    100.0,
                    (rec.ideal_cycle_time * rec.total_units / rec.run_time)
                    * 100.0,
                )
            qual = (
                (rec.good_units / rec.total_units) * 100.0
                if rec.total_units else 0.0
            )
            rec.availability = round(avail, 2)
            rec.performance = round(perf, 2)
            rec.quality = round(qual, 2)
            rec.oee = round(avail * perf * qual / 10000.0, 2)
