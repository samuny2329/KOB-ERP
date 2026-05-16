"""KPI scorecard per plan run.

Each `thiti.plan.run` exposes one `thiti.kpi` record computed from the
output models (`thiti.plan.operation`, `thiti.plan.demand.peg`,
`thiti.plan.resource.load`, `thiti.plan.buffer.projection`,
`thiti.plan.problem`).

KPIs:
- service_level_pct = on-time pegs / total pegs
- average_delay_days
- capacity_utilization_pct (weighted by available_hours)
- resource_overload_count
- buffer_shortage_count
- forecast_accuracy_pct (MAPE-based, when forecast records exist)
- plan_cost (sum of operation costs)
"""
from __future__ import annotations

from odoo import api, fields, models


class ThitiKpi(models.Model):
    _name = "thiti.kpi"
    _description = "Thiti Plan KPI Scorecard"
    _order = "run_id desc"
    _rec_name = "run_id"

    run_id = fields.Many2one(
        "thiti.plan.run", required=True, index=True, ondelete="cascade",
    )
    create_date = fields.Datetime(readonly=True)

    total_demands = fields.Integer(readonly=True)
    on_time_demands = fields.Integer(readonly=True)
    late_demands = fields.Integer(readonly=True)
    service_level_pct = fields.Float(readonly=True, group_operator="avg")
    average_delay_days = fields.Float(readonly=True, group_operator="avg")
    max_delay_days = fields.Float(readonly=True)

    total_operations = fields.Integer(readonly=True)
    total_replenishments = fields.Integer(readonly=True)
    po_count = fields.Integer(readonly=True)
    mo_count = fields.Integer(readonly=True)
    do_count = fields.Integer(readonly=True)

    capacity_utilization_pct = fields.Float(readonly=True, group_operator="avg")
    resource_overload_count = fields.Integer(readonly=True)
    avg_resource_idle_pct = fields.Float(readonly=True, group_operator="avg")

    buffer_shortage_count = fields.Integer(readonly=True)
    buffer_below_safety_count = fields.Integer(readonly=True)

    forecast_mape_pct = fields.Float(readonly=True, group_operator="avg")
    forecast_bias = fields.Float(readonly=True, group_operator="avg")

    problem_critical = fields.Integer(readonly=True)
    problem_error = fields.Integer(readonly=True)
    problem_warning = fields.Integer(readonly=True)

    plan_cost = fields.Monetary(readonly=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id,
    )

    _sql_constraints = [
        ("run_unique", "UNIQUE(run_id)",
         "Only one KPI record per plan run."),
    ]

    @api.model
    def recompute_for_run(self, run) -> "ThitiKpi":
        existing = self.search([("run_id", "=", run.id)], limit=1)
        vals = self._compute_vals(run)
        if existing:
            existing.write(vals)
            return existing
        vals["run_id"] = run.id
        return self.create(vals)

    def _compute_vals(self, run) -> dict:
        pegs = self.env["thiti.plan.demand.peg"].search([("run_id", "=", run.id)])
        late_pegs = pegs.filtered(lambda p: p.delay_days and p.delay_days > 0)
        total_pegs = len(pegs)
        on_time = total_pegs - len(late_pegs)
        delays = pegs.mapped("delay_days") or [0.0]
        service_level = (on_time / total_pegs * 100.0) if total_pegs else 100.0
        avg_delay = sum(delays) / len(delays) if delays else 0.0
        max_delay = max(delays) if delays else 0.0

        ops = self.env["thiti.plan.operation"].search([("run_id", "=", run.id)])
        total_ops = len(ops)

        reps = self.env["thiti.plan.replenishment"].search([("run_id", "=", run.id)])
        po_count = sum(1 for r in reps if r.kind == "po" and r.state == "created")
        mo_count = sum(1 for r in reps if r.kind == "mo" and r.state == "created")
        do_count = sum(1 for r in reps if r.kind == "do" and r.state == "created")

        loads = self.env["thiti.plan.resource.load"].search([("run_id", "=", run.id)])
        total_avail = sum(loads.mapped("available_hours")) or 0.0
        total_loaded = sum(loads.mapped("loaded_hours")) or 0.0
        util = (total_loaded / total_avail * 100.0) if total_avail else 0.0
        overload = sum(1 for l in loads if (l.utilization_pct or 0) > 100)
        idle = sum(1 for l in loads if (l.utilization_pct or 0) < 50) / (len(loads) or 1) * 100.0

        projs = self.env["thiti.plan.buffer.projection"].search([
            ("run_id", "=", run.id),
        ])
        shortages = sum(1 for p in projs if (p.shortage_qty or 0) > 0)
        below_safety = sum(1 for p in projs if p.below_safety)

        problems = self.env["thiti.plan.problem"].search([("run_id", "=", run.id)])
        crit = sum(1 for p in problems if p.severity == "critical")
        errs = sum(1 for p in problems if p.severity == "error")
        warns = sum(1 for p in problems if p.severity == "warning")

        forecasts = self.env["thiti.forecast"].search([])
        mapes = [f.mape for f in forecasts if f.mape]
        biases = [f.bias for f in forecasts if f.bias]
        fc_mape = sum(mapes) / len(mapes) if mapes else 0.0
        fc_bias = sum(biases) / len(biases) if biases else 0.0

        plan_cost = sum(reps.mapped("cost") or [0.0])

        return {
            "total_demands": total_pegs,
            "on_time_demands": on_time,
            "late_demands": len(late_pegs),
            "service_level_pct": service_level,
            "average_delay_days": avg_delay,
            "max_delay_days": max_delay,
            "total_operations": total_ops,
            "total_replenishments": len(reps),
            "po_count": po_count,
            "mo_count": mo_count,
            "do_count": do_count,
            "capacity_utilization_pct": util,
            "resource_overload_count": overload,
            "avg_resource_idle_pct": idle,
            "buffer_shortage_count": shortages,
            "buffer_below_safety_count": below_safety,
            "forecast_mape_pct": fc_mape,
            "forecast_bias": fc_bias,
            "problem_critical": crit,
            "problem_error": errs,
            "problem_warning": warns,
            "plan_cost": plan_cost,
        }
