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
    oee_date = fields.Date(
        required=True, default=fields.Date.context_today,
        help="Production date for which OEE is being computed. Usually 1 row "
             "per (workcenter, shift, date).",
    )
    planned_time = fields.Integer(
        help="Minutes scheduled for production in this shift "
             "(e.g. 8-hour shift = 480 min).",
    )
    available_time = fields.Integer(
        help="Minutes machine was actually available (planned − unplanned "
             "downtime). Used to compute Availability %.",
    )
    run_time = fields.Integer(
        help="Minutes the machine was producing (available − idle/setup time). "
             "Used to compute Performance %.",
    )
    ideal_cycle_time = fields.Float(
        digits=(8, 4),
        help="Ideal minutes per unit at design speed (theoretical maximum). "
             "Used to compute Performance % vs actual cycle time.",
    )
    total_units = fields.Integer(
        help="All units produced in the shift (good + reject + rework). "
             "Numerator for Performance and denominator for Quality.",
    )
    good_units = fields.Integer(
        help="First-pass-yield units that passed QC. Numerator for Quality %. "
             "Diff vs total_units = scrap/rework count.",
    )
    availability = fields.Float(
        digits=(5, 2), compute="_compute_oee", store=True,
        help="Availability % = (available_time / planned_time) × 100. "
             "Measures uptime vs schedule. World-class: ≥90%. "
             "🟢 ≥85% · 🟡 70–85% · 🔴 <70% breakdowns/changeovers issue.",
    )
    performance = fields.Float(
        digits=(5, 2), compute="_compute_oee", store=True,
        help="Performance % = (ideal_cycle × total_units) / run_time × 100. "
             "Measures speed vs design. World-class: ≥95%. "
             "🟢 ≥90% · 🟡 75–90% · 🔴 <75% — slow running, micro-stops.",
    )
    quality = fields.Float(
        digits=(5, 2), compute="_compute_oee", store=True,
        help="Quality % = (good_units / total_units) × 100. First-pass yield. "
             "World-class: ≥99.9%. 🟢 ≥98% · 🟡 95–98% · 🔴 <95%.",
    )
    oee = fields.Float(
        digits=(5, 2), compute="_compute_oee", store=True,
        help="OEE = Availability × Performance × Quality / 10,000. "
             "Industry benchmarks: World-class ≥85%, Excellent 75–85%, "
             "Average 60–75%, Low <60%. KOB cosmetics target: 70%+.",
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
