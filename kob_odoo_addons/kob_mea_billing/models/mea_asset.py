# -*- coding: utf-8 -*-
"""Asset (equipment) tracking + savings plan for each MEA meter site.

Goal: identify which devices drive the bill, compute their kWh footprint
(per hour / day / month), and stage cost-reduction actions with payback.

Empirical conversion factors (verified against KK16 HVAC bills):
- 1 BTU/hr ≈ 0.293 W (cooling capacity unit)
- Non-inverter AC EER ~ 9-11 W/W → input power = BTU / EER
- Inverter AC EER ~ 16-22 → input power = BTU / EER
"""
from odoo import api, fields, models


# Defaults for typical Thai commercial equipment
EER_NON_INVERTER = 10.0     # W/W (cooling per electrical input)
EER_INVERTER = 18.0
TARIFF_BLENDED_THB_PER_KWH = 4.50   # rough average across TOU + flat for ROI calc


class MeaAssetCategory(models.Model):
    _name = "mea.asset.category"
    _description = "MEA Asset Category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Short code (HVAC, MOTOR, LIGHT, IT, PUMP, FIRE, OTHER).")
    sequence = fields.Integer(default=10)
    icon = fields.Char(default="fa-bolt", help="Font Awesome icon class for display.")
    typical_load_pct = fields.Float(
        string="Typical Bill Share (%)",
        digits=(5, 2),
        help="Empirical share of total bill this category usually drives "
             "(reference only). Example: HVAC ~70-85% in Thai warehouses.",
    )
    color = fields.Integer(string="Color Index", default=0)

    _sql_constraints = [("uniq_code", "unique(code)", "Category code must be unique.")]


class MeaAsset(models.Model):
    _name = "mea.asset"
    _description = "MEA Site Asset (Power Consumer)"
    _order = "meter_id, category_id, name"
    _inherit = ["mail.thread"]

    # ---------- Identity ----------
    name = fields.Char(
        required=True, tracking=True,
        help="Free-text label, e.g. 'Daikin Inverter 36000 BTU - Hall A'.",
    )
    asset_code = fields.Char(
        help="Internal asset code (optional). Useful for matching with a "
             "fixed asset register elsewhere.",
    )
    meter_id = fields.Many2one(
        "mea.meter", required=True, ondelete="cascade", index=True,
        help="The MEA meter this asset draws power from.",
    )
    company_id = fields.Many2one(
        "res.company", related="meter_id.company_id", store=True,
    )
    site_short = fields.Char(related="meter_id.site_short", store=True)
    category_id = fields.Many2one(
        "mea.asset.category", required=True,
        help="Equipment category. Drives default formulas + grouping in "
             "savings plan reports.",
    )
    brand = fields.Char(help="Manufacturer (Daikin / Mitsubishi / Carrier / ...).")
    model_no = fields.Char(string="Model", help="OEM model number from nameplate.")
    serial_no = fields.Char(help="Serial number for warranty / asset-tracking.")
    qty = fields.Integer(
        default=1, required=True,
        help="Number of identical units sharing the same spec (e.g. 2 ACs).",
    )

    # ---------- Power rating ----------
    rating_btu = fields.Integer(
        string="Cooling Capacity (BTU/hr)",
        help="HVAC: nameplate cooling capacity. "
             "1 ton ≈ 12,000 BTU/hr ≈ 3,517 W of cooling effect "
             "(NOT the same as electrical input power).",
    )
    is_inverter = fields.Boolean(
        help="True for inverter-driven HVAC. Improves EER from ~10 to ~18 (+80%).",
    )
    eer = fields.Float(
        string="EER (W/W)", digits=(6, 2),
        help="Energy Efficiency Ratio = cooling output ÷ electrical input. "
             "Higher = more efficient. Typical: non-inverter 9-11, inverter 16-22.",
    )
    rating_w = fields.Integer(
        string="Power Input (W)",
        compute="_compute_power_w", store=True, readonly=False,
        help="Rated electrical input per unit. Auto-estimated from BTU÷EER for "
             "HVAC. Override manually when nameplate data is available.",
    )
    total_rating_w = fields.Integer(
        compute="_compute_power_w", store=True,
        help="rating_w × qty — total instantaneous load when all units run.",
    )

    # ---------- Operating profile ----------
    hours_per_day = fields.Float(
        digits=(5, 2), default=8.0,
        help="Average run hours per day (full-load equivalent). "
             "Cooling: 8h business hours. 24/7 IT: 24h. Pump on-demand: 0.5-2h.",
    )
    days_per_month = fields.Float(
        digits=(5, 2), default=22.0,
        help="Operating days per month. 22 = weekdays only, 30 = continuous.",
    )
    duty_cycle = fields.Float(
        string="Duty Cycle (%)", digits=(5, 2), default=70.0,
        help="Fraction of run-time the unit actually consumes its rated power. "
             "Inverter AC ~50-70% (modulates), non-inverter ~80-100% (on/off), "
             "fans ~100% when on.",
    )

    # ---------- Computed consumption ----------
    kwh_per_hour = fields.Float(
        compute="_compute_kwh", store=True, digits=(10, 3),
        help="kWh consumed per hour of operation. "
             "Formula: total_rating_w × duty_cycle / 1000 / 100",
    )
    kwh_per_day = fields.Float(
        compute="_compute_kwh", store=True, digits=(10, 2),
        help="Formula: kwh_per_hour × hours_per_day",
    )
    kwh_per_month = fields.Float(
        compute="_compute_kwh", store=True, digits=(10, 2),
        help="Formula: kwh_per_day × days_per_month",
    )
    cost_per_month = fields.Float(
        compute="_compute_kwh", store=True, digits=(12, 2),
        help="Formula: kwh_per_month × blended_rate (default 4.50 THB/kWh, "
             "adjustable via system parameter 'kob_mea.blended_rate').",
    )
    bill_share_pct = fields.Float(
        compute="_compute_kwh", store=True, digits=(5, 2),
        help="Estimated % of meter's monthly bill driven by this asset. "
             "Computed against the meter's 12-month average total amount.",
    )

    # ---------- Asset registry ----------
    purchase_date = fields.Date()
    purchase_cost = fields.Float(digits=(12, 2), help="Acquisition cost (THB).")
    expected_lifespan_years = fields.Integer(default=10)
    note = fields.Text()
    state = fields.Selection(
        [("active", "Active"), ("standby", "Standby"), ("retired", "Retired")],
        default="active", tracking=True,
    )

    # ---------- Savings plan ----------
    action_ids = fields.One2many("mea.asset.action", "asset_id")
    action_count = fields.Integer(compute="_compute_action_count")
    potential_savings_thb = fields.Float(
        compute="_compute_potential_savings", store=True, digits=(12, 2),
        help="Sum of all proposed/approved actions' annual_savings_thb.",
    )

    # ---------- Compute methods ----------
    @api.depends("rating_btu", "eer", "is_inverter", "rating_w", "qty")
    def _compute_power_w(self):
        for r in self:
            # Auto-estimate rating_w when BTU is set but rating_w not overridden
            if r.rating_btu and not r.rating_w:
                eer = r.eer or (EER_INVERTER if r.is_inverter else EER_NON_INVERTER)
                r.rating_w = int(r.rating_btu / eer) if eer else 0
            r.total_rating_w = (r.rating_w or 0) * (r.qty or 1)

    @api.depends("total_rating_w", "duty_cycle", "hours_per_day", "days_per_month",
                 "meter_id", "meter_id.bill_history_ids.total_amount")
    def _compute_kwh(self):
        rate = float(self.env["ir.config_parameter"].sudo().get_param(
            "kob_mea.blended_rate", default=str(TARIFF_BLENDED_THB_PER_KWH),
        ))
        for r in self:
            duty = (r.duty_cycle or 100.0) / 100.0
            r.kwh_per_hour = (r.total_rating_w or 0) * duty / 1000.0
            r.kwh_per_day = r.kwh_per_hour * (r.hours_per_day or 0)
            r.kwh_per_month = r.kwh_per_day * (r.days_per_month or 0)
            r.cost_per_month = r.kwh_per_month * rate

            # Bill share: against meter's last 12 bills' avg total_amount
            bills = r.meter_id.bill_history_ids[:12]
            if bills:
                avg_bill = sum(b.total_amount for b in bills) / len(bills)
                r.bill_share_pct = (r.cost_per_month / avg_bill) * 100.0 if avg_bill else 0.0
            else:
                r.bill_share_pct = 0.0

    @api.depends("action_ids")
    def _compute_action_count(self):
        for r in self:
            r.action_count = len(r.action_ids)

    @api.depends("action_ids.annual_savings_thb", "action_ids.state")
    def _compute_potential_savings(self):
        for r in self:
            r.potential_savings_thb = sum(
                a.annual_savings_thb for a in r.action_ids
                if a.state in ("proposed", "approved", "in_progress")
            )

    # ---------- Actions ----------
    def action_view_actions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Saving Actions – {self.name}",
            "res_model": "mea.asset.action",
            "view_mode": "list,form",
            "domain": [("asset_id", "=", self.id)],
            "context": {"default_asset_id": self.id},
        }


class MeaAssetAction(models.Model):
    _name = "mea.asset.action"
    _description = "MEA Asset Cost-Reduction Action"
    _order = "priority desc, payback_months"
    _inherit = ["mail.thread"]

    name = fields.Char(
        required=True, tracking=True,
        help="Short title (e.g. 'Replace Daikin 36k non-inverter with inverter').",
    )
    asset_id = fields.Many2one(
        "mea.asset", required=True, ondelete="cascade", index=True,
    )
    meter_id = fields.Many2one(related="asset_id.meter_id", store=True, index=True)
    site_short = fields.Char(related="asset_id.site_short", store=True)
    category_id = fields.Many2one(related="asset_id.category_id", store=True)

    action_type = fields.Selection(
        [("replace", "Replace with Efficient Model"),
         ("upgrade", "Upgrade Component (e.g. add inverter)"),
         ("schedule", "Schedule Optimization (off-peak shift)"),
         ("maintenance", "Preventive Maintenance"),
         ("control", "Smart Control / Sensor / BMS"),
         ("solar", "Solar PV Offset"),
         ("retire", "Retire / Decommission")],
        required=True, default="replace",
        help="Type of intervention. Drives default duration + risk profile.",
    )

    description = fields.Text(
        help="Detailed plan: scope, vendor, lead time, dependencies.",
    )
    priority = fields.Selection(
        [("0", "Low"), ("1", "Medium"), ("2", "High"), ("3", "Critical")],
        default="1", tracking=True,
    )

    # ---------- Savings model ----------
    target_pct_saving = fields.Float(
        string="Energy Saving Target (%)", digits=(5, 2),
        help="Expected reduction in this asset's kWh after the action. "
             "Inverter retrofit: 30-40%. LED replace: 50-70%. Solar: 30-50%.",
    )
    annual_savings_kwh = fields.Float(
        compute="_compute_savings", store=True, digits=(12, 2),
        help="Formula: asset.kwh_per_month × 12 × target_pct_saving / 100",
    )
    annual_savings_thb = fields.Float(
        compute="_compute_savings", store=True, digits=(12, 2),
        help="Formula: annual_savings_kwh × blended_rate (THB/kWh)",
    )

    # ---------- Capex + payback ----------
    capex_required = fields.Float(
        digits=(12, 2),
        help="One-time investment (THB). Covers equipment + installation.",
    )
    payback_months = fields.Float(
        compute="_compute_savings", store=True, digits=(8, 1),
        help="Formula: capex_required ÷ (annual_savings_thb ÷ 12). "
             "Smaller = faster ROI. Typical good: < 36 months.",
    )

    # ---------- State + dates ----------
    state = fields.Selection(
        [("draft", "Draft"),
         ("proposed", "Proposed"),
         ("approved", "Approved"),
         ("in_progress", "In Progress"),
         ("completed", "Completed"),
         ("cancelled", "Cancelled")],
        default="draft", tracking=True, index=True,
    )
    target_date = fields.Date(help="Planned completion date.")
    completed_date = fields.Date()
    note = fields.Text()

    @api.depends("asset_id.kwh_per_month", "target_pct_saving", "capex_required")
    def _compute_savings(self):
        rate = float(self.env["ir.config_parameter"].sudo().get_param(
            "kob_mea.blended_rate", default=str(TARIFF_BLENDED_THB_PER_KWH),
        ))
        for r in self:
            r.annual_savings_kwh = (
                (r.asset_id.kwh_per_month or 0) * 12.0 * (r.target_pct_saving or 0) / 100.0
            )
            r.annual_savings_thb = r.annual_savings_kwh * rate
            monthly_savings = r.annual_savings_thb / 12.0 if r.annual_savings_thb else 0
            r.payback_months = (
                (r.capex_required / monthly_savings) if monthly_savings else 0.0
            )

    def action_propose(self):
        self.write({"state": "proposed"})

    def action_approve(self):
        self.write({"state": "approved"})

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_complete(self):
        for r in self:
            r.write({"state": "completed", "completed_date": fields.Date.today()})

    def action_cancel(self):
        self.write({"state": "cancelled"})
