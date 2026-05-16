"""Scenario / what-if container.

Plan runs (and indirectly their outputs) are tagged with a `scenario_id`.
Users can clone the baseline scenario, tweak parameters (e.g. capacity,
demand spikes, lead times), trigger a new plan run, and compare side-by-side.

Implementation pattern: single DB, scenario-scoped queries — every plan
run belongs to exactly one scenario; default scenario "Baseline" auto-created.
"""
from __future__ import annotations

from odoo import _, api, fields, models


class ThitiScenario(models.Model):
    _name = "thiti.scenario"
    _description = "Thiti Planning Scenario / What-if"
    _inherit = ["mail.thread"]
    _order = "is_baseline desc, name"

    name = fields.Char(required=True, index=True, tracking=True)
    description = fields.Text(tracking=True)
    is_baseline = fields.Boolean(
        default=False, tracking=True,
        help="The baseline scenario reflects actual Odoo data without overrides.",
    )
    parent_id = fields.Many2one(
        "thiti.scenario", string="Cloned From", index=True,
    )
    capacity_factor = fields.Float(
        default=1.0, tracking=True,
        help="Multiplier applied to resource capacity (1.0 = baseline). "
             "Use 0.8 to simulate a 20%% capacity cut.",
    )
    demand_factor = fields.Float(
        default=1.0, tracking=True,
        help="Multiplier applied to demand quantities.",
    )
    leadtime_factor = fields.Float(
        default=1.0, tracking=True,
        help="Multiplier applied to supplier lead times.",
    )
    plan_run_ids = fields.One2many("thiti.plan.run", "scenario_id", string="Plan Runs")
    run_count = fields.Integer(compute="_compute_run_count")
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         "Scenario name must be unique per company."),
    ]

    @api.depends("plan_run_ids")
    def _compute_run_count(self):
        for rec in self:
            rec.run_count = len(rec.plan_run_ids)

    def action_clone(self):
        self.ensure_one()
        new = self.copy({
            "name": _("%s (clone)") % self.name,
            "is_baseline": False,
            "parent_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": new.id,
            "view_mode": "form",
        }

    def action_run_plan(self):
        """Create + execute a plan run under this scenario."""
        self.ensure_one()
        run = self.env["thiti.plan.run"].create({
            "name": _("Plan / %s / %s") % (self.name, fields.Datetime.now()),
            "scenario_id": self.id,
        })
        run.action_run()
        return {
            "type": "ir.actions.act_window",
            "res_model": "thiti.plan.run",
            "res_id": run.id,
            "view_mode": "form",
        }


class ThitiScenarioCompare(models.TransientModel):
    _name = "thiti.scenario.compare"
    _description = "Thiti Scenario Compare Wizard"

    scenario_left_id = fields.Many2one(
        "thiti.scenario", required=True, string="Scenario A",
    )
    scenario_right_id = fields.Many2one(
        "thiti.scenario", required=True, string="Scenario B",
    )
    run_left_id = fields.Many2one(
        "thiti.plan.run", string="Run A",
        domain="[('scenario_id','=',scenario_left_id)]",
    )
    run_right_id = fields.Many2one(
        "thiti.plan.run", string="Run B",
        domain="[('scenario_id','=',scenario_right_id)]",
    )
    sl_left = fields.Float(string="Service Level A (%)", readonly=True)
    sl_right = fields.Float(string="Service Level B (%)", readonly=True)
    util_left = fields.Float(string="Utilization A (%)", readonly=True)
    util_right = fields.Float(string="Utilization B (%)", readonly=True)
    cost_left = fields.Monetary(readonly=True)
    cost_right = fields.Monetary(readonly=True)
    delay_left = fields.Float(readonly=True)
    delay_right = fields.Float(readonly=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id,
    )

    def action_compare(self):
        self.ensure_one()
        kpi_left = self.env["thiti.kpi"].search(
            [("run_id", "=", self.run_left_id.id)], limit=1,
        )
        kpi_right = self.env["thiti.kpi"].search(
            [("run_id", "=", self.run_right_id.id)], limit=1,
        )
        self.write({
            "sl_left": kpi_left.service_level_pct if kpi_left else 0.0,
            "sl_right": kpi_right.service_level_pct if kpi_right else 0.0,
            "util_left": kpi_left.capacity_utilization_pct if kpi_left else 0.0,
            "util_right": kpi_right.capacity_utilization_pct if kpi_right else 0.0,
            "cost_left": kpi_left.plan_cost if kpi_left else 0.0,
            "cost_right": kpi_right.plan_cost if kpi_right else 0.0,
            "delay_left": kpi_left.average_delay_days if kpi_left else 0.0,
            "delay_right": kpi_right.average_delay_days if kpi_right else 0.0,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
