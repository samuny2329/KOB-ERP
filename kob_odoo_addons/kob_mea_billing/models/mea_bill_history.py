# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MeaBillHistory(models.Model):
    _name = "mea.bill.history"
    _description = "MEA Monthly Bill History"
    _order = "billing_month desc, meter_id"
    _inherit = ["mail.thread"]

    meter_id = fields.Many2one(
        "mea.meter",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="meter_id.company_id",
        store=True,
        index=True,
    )
    site_short = fields.Char(related="meter_id.site_short", store=True)
    tariff_id = fields.Many2one(related="meter_id.tariff_id", store=True)
    is_tou = fields.Boolean(related="meter_id.is_tou", store=True)

    billing_month = fields.Date(
        required=True,
        index=True,
        help="First day of the billing month (e.g. 2026-04-01 for April 2026). "
             "Must always be the 1st — enforced by constraint.",
    )
    invoice_no = fields.Char(
        string="MEA Invoice No.",
        help="Ref No.2 on the MEA bill — unique 11-digit invoice identifier "
             "issued by MEA for this billing period.",
    )
    reading_date_start = fields.Date(
        help="Date the meter reading was taken at the START of the billing cycle "
             "(usually 30 days before reading_date_end).",
    )
    reading_date_end = fields.Date(
        help="Date the meter reading was taken at the END of the billing cycle. "
             "kWh used = (kwh_curr at this date) − (kwh_prev at start date).",
    )
    kwh_prev = fields.Float(
        string="Previous Reading", digits=(12, 2),
        help="Meter reading at the start of the period (lower number).",
    )
    kwh_curr = fields.Float(
        string="Current Reading", digits=(12, 2),
        help="Meter reading at the end of the period (higher number).",
    )
    kwh_total = fields.Float(
        string="kWh Used", digits=(12, 2), tracking=True,
        help="Energy consumed in the period: kwh_curr − kwh_prev.",
    )
    kwh_on_peak = fields.Float(
        string="On-Peak kWh", digits=(12, 2),
        help="On-peak kWh (TOU only). Peak = Mon-Fri 09:00-22:00. "
             "Charged at higher rate (4.33 THB/kWh for tariff 3.2.3).",
    )
    kwh_off_peak = fields.Float(
        string="Off-Peak kWh", digits=(12, 2),
        help="Off-peak kWh (TOU only). Off-peak = nights, weekends, holidays. "
             "Charged at lower rate (2.64 THB/kWh for tariff 3.2.3).",
    )
    demand_on_peak = fields.Float(
        string="On-Peak Demand (kW)", digits=(8, 2),
        help="Highest 15-minute average demand during on-peak hours (TOU only). "
             "MEA charges Demand × 210 THB/kW for tariff 3.2.3.",
    )
    demand_off_peak = fields.Float(
        string="Off-Peak Demand (kW)", digits=(8, 2),
        help="Highest 15-minute average demand during off-peak hours. "
             "Informational — not used for charge calculation.",
    )

    energy_charge = fields.Float(
        string="Energy Charge", digits=(12, 2),
        help="Energy cost from the bill: kWh × rate. "
             "TOU: on×peak_rate + off×off_peak_rate. Flat: progressive tier sum.",
    )
    demand_charge = fields.Float(
        string="Demand Charge", digits=(12, 2),
        help="Demand cost (TOU only): demand_on_peak × tariff.demand_charge.",
    )
    service_charge = fields.Float(
        string="Service Charge", digits=(12, 2),
        help="Fixed monthly service fee (e.g. 312.24 THB for TOU 3.2.3, "
             "33.29 THB for Flat 2.1.2). Charged regardless of usage.",
    )
    pf_charge = fields.Float(
        string="Power Factor Charge", digits=(12, 2),
        help="Penalty when power factor < 0.85. Calculated as kVAr "
             "exceeding 61.97% of peak kW × penalty rate.",
    )
    ft_rate = fields.Float(
        string="Ft (THB/kWh)", digits=(8, 4),
        help="Ft (Fuel Tariff Adjustment) rate in THB per kWh. "
             "ERC publishes quarterly. Stored here in THB form (e.g. 0.0972) — "
             "the bill prints satang (e.g. 9.72 stang/kWh) which is /100 of this.",
    )
    ft_amount = fields.Float(
        string="Ft Amount", digits=(12, 2),
        help="Total Ft surcharge for the month: kWh × ft_rate.",
    )
    subtotal = fields.Float(
        string="Subtotal (Pre-VAT)", digits=(12, 2),
        help="Energy + Demand + Service + Power Factor + Ft. "
             "Excluded VAT 7%.",
    )
    vat_amount = fields.Float(
        string="VAT", digits=(12, 2),
        help="Value Added Tax 7% applied to subtotal.",
    )
    total_amount = fields.Float(
        string="Total (THB)", digits=(12, 2), tracking=True,
        help="Final billed amount: subtotal + VAT. "
             "Equals 'รวมเงินที่ต้องชำระทั้งสิ้น' on the printed MEA bill.",
    )

    expected_amount = fields.Float(
        string="Expected (Calculator)",
        digits=(12, 2),
        compute="_compute_expected",
        store=True,
        help="Predicted total from mea.calculator using kWh + tariff + Ft. "
             "Useful to detect billing errors or anomalous consumption "
             "before paying. Computed automatically on save.",
    )
    expected_breakdown = fields.Text(
        compute="_compute_expected",
        store=True,
        help="Per-component breakdown: energy / service / Ft / VAT / Ft rate. "
             "Helps audit which charge component drives the expected total.",
    )
    variance = fields.Float(
        compute="_compute_variance", store=True, digits=(12, 2),
        help="Absolute difference: actual − expected (THB). "
             "Positive = paying more than expected.",
    )
    variance_pct = fields.Float(
        compute="_compute_variance", store=True, digits=(8, 2),
        help="Relative difference: (actual − expected) ÷ expected × 100. "
             "Negative = under-charged; positive = over-charged vs model.",
    )
    is_anomaly = fields.Boolean(
        compute="_compute_variance", store=True,
        help="True when |variance_pct| exceeds the anomaly threshold "
             "(default 20%, configurable via system parameter "
             "'kob_mea.anomaly_pct'). Flagged for manual review.",
    )

    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Source PDF",
        help="MEA bill PDF this record was extracted from.",
    )
    source = fields.Selection(
        [("pdf_extract", "PDF Extract"), ("manual", "Manual Entry"), ("portal", "Portal Scrape")],
        default="manual",
    )
    extraction_confidence = fields.Float(
        digits=(3, 2),
        help="0.0 – 1.0 confidence from PDF extractor. <0.7 → state=manual_review.",
    )
    state = fields.Selection(
        [("draft", "Draft"),
         ("confirmed", "Confirmed"),
         ("anomaly", "Anomaly"),
         ("manual_review", "Manual Review")],
        default="draft",
        tracking=True,
        index=True,
    )
    note = fields.Text()
    raw_text = fields.Text(help="Raw text dump from PDF extractor (debug only).")

    # ---------- Throughput linkage (online warehouses operating at this site) ----------
    order_qty_btv_wh2 = fields.Integer(
        string="BTV-WH2 Orders",
        tracking=True,
        help="Quantity of units shipped via 'BTV-WH2 Delivery Orders' "
             "during this billing month. Imported from stock.move xlsx export. "
             "Relevant for sites where BTV warehouse physically operates "
             "(e.g. KK-16 hub).",
    )
    order_qty_kob_wh2 = fields.Integer(
        string="KOB-WH2 Orders",
        tracking=True,
        help="Quantity of units shipped via 'KOB-WH2 Delivery Orders' "
             "during this billing month. Imported from stock.move xlsx export.",
    )
    order_qty_total = fields.Integer(
        string="Total Orders",
        compute="_compute_order_qty_total",
        store=True,
        help="Sum of BTV-WH2 + KOB-WH2 delivery orders for the month. "
             "Used to compute kWh-per-order and cost-per-order metrics.",
    )
    is_throughput_outlier = fields.Boolean(
        string="Throughput Outlier",
        help="Flag months with abnormal qty (e.g. ramp-up, partial month, holiday). "
             "Excluded from average per-order metrics in dashboards.",
    )

    kwh_per_order = fields.Float(
        string="kWh / Order",
        digits=(8, 4),
        compute="_compute_throughput_metrics",
        store=True,
        help="Energy intensity: kwh_total ÷ order_qty_total. "
             "Lower = more efficient pick/pack operation.",
    )
    cost_per_order = fields.Float(
        string="Cost / Order (THB)",
        digits=(8, 4),
        compute="_compute_throughput_metrics",
        store=True,
        help="Electricity cost burden per shipped unit: total_amount ÷ order_qty_total.",
    )
    demand_per_kqty = fields.Float(
        string="Peak Demand / 1k Orders (kW)",
        digits=(8, 4),
        compute="_compute_throughput_metrics",
        store=True,
        help="Peak load efficiency: demand_on_peak ÷ (order_qty_total / 1000). "
             "Useful to assess whether peak kW grows linearly with throughput.",
    )

    # ---------- OT linkage (Online-team overtime hours, proxy for off-hours operations) ----------
    # Standard work hours 08:00-17:00. OT = work outside this window.
    # OT hours correlate with off-peak kWh (HVAC + lighting kept on past 17:00
    # or before 08:00, weekends). Helps explain elevated off_peak kWh and
    # suggests scheduling moves to flatten demand.
    ot_hours_online = fields.Float(
        string="OT Hours",
        digits=(10, 2),
        tracking=True,
        help="Total overtime hours logged by warehouse staff for this "
             "billing month. Imported from HR OT export (OT 69.xlsx). "
             "Default import filters Online-team departments; configurable "
             "per site for non-online warehouses.",
    )
    ot_employee_count = fields.Integer(
        string="OT Employees",
        help="Distinct number of employees who logged any OT during the month.",
    )
    kwh_per_ot_hour = fields.Float(
        string="kWh / OT Hour",
        digits=(10, 4),
        compute="_compute_ot_metrics",
        store=True,
        help="Off-hours energy intensity proxy: kwh_off_peak ÷ ot_hours_online. "
             "Falls back to kwh_total when off-peak split is missing.",
    )
    cost_per_ot_hour = fields.Float(
        string="Cost / OT Hour (THB)",
        digits=(10, 4),
        compute="_compute_ot_metrics",
        store=True,
        help="Indicative cost of running facility per overtime hour: "
             "total_amount ÷ ot_hours_online.",
    )
    orders_per_ot_hour = fields.Float(
        string="Orders / OT Hour",
        digits=(10, 2),
        compute="_compute_ot_metrics",
        store=True,
        help="Throughput per OT hour: order_qty_total ÷ ot_hours_online. "
             "Higher = OT used more productively.",
    )

    _sql_constraints = [
        ("uniq_meter_month", "unique(meter_id, billing_month)",
         "One bill per meter per month only."),
    ]

    # ---------- Computed ----------
    @api.depends("meter_id", "billing_month", "kwh_total", "kwh_on_peak", "kwh_off_peak",
                 "demand_on_peak")
    def _compute_expected(self):
        calc = self.env["mea.calculator"]
        for r in self:
            if not (r.meter_id and r.billing_month and r.kwh_total):
                r.expected_amount = 0.0
                r.expected_breakdown = ""
                continue
            try:
                result = calc._compute_expected(
                    r.meter_id,
                    r.billing_month,
                    {
                        "total": r.kwh_total,
                        "on_peak": r.kwh_on_peak,
                        "off_peak": r.kwh_off_peak,
                        "demand_kw": r.demand_on_peak,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                r.expected_amount = 0.0
                r.expected_breakdown = f"ERROR: {exc}"
                continue
            r.expected_amount = result.get("total") or 0.0
            r.expected_breakdown = (
                f"energy={result.get('energy', 0):.2f} | "
                f"service={result.get('service', 0):.2f} | "
                f"ft={result.get('ft', 0):.2f} | "
                f"vat={result.get('vat', 0):.2f} | "
                f"ft_rate_satang={result.get('ft_rate_satang', 0):.2f}"
            )

    @api.depends("order_qty_btv_wh2", "order_qty_kob_wh2")
    def _compute_order_qty_total(self):
        for r in self:
            r.order_qty_total = (r.order_qty_btv_wh2 or 0) + (r.order_qty_kob_wh2 or 0)

    @api.depends("kwh_total", "total_amount", "demand_on_peak", "order_qty_total")
    def _compute_throughput_metrics(self):
        for r in self:
            qty = r.order_qty_total or 0
            if qty <= 0:
                r.kwh_per_order = 0.0
                r.cost_per_order = 0.0
                r.demand_per_kqty = 0.0
                continue
            r.kwh_per_order = (r.kwh_total or 0.0) / qty
            r.cost_per_order = (r.total_amount or 0.0) / qty
            r.demand_per_kqty = (r.demand_on_peak or 0.0) / (qty / 1000.0)

    @api.depends("kwh_total", "kwh_off_peak", "total_amount", "order_qty_total",
                 "ot_hours_online")
    def _compute_ot_metrics(self):
        for r in self:
            ot = r.ot_hours_online or 0.0
            if ot <= 0:
                r.kwh_per_ot_hour = 0.0
                r.cost_per_ot_hour = 0.0
                r.orders_per_ot_hour = 0.0
                continue
            kwh_basis = r.kwh_off_peak if r.kwh_off_peak else (r.kwh_total or 0.0)
            r.kwh_per_ot_hour = kwh_basis / ot
            r.cost_per_ot_hour = (r.total_amount or 0.0) / ot
            r.orders_per_ot_hour = (r.order_qty_total or 0.0) / ot

    @api.depends("total_amount", "expected_amount")
    def _compute_variance(self):
        threshold = float(
            self.env["ir.config_parameter"].sudo().get_param(
                "kob_mea.anomaly_pct", default="20"
            )
        )
        for r in self:
            if r.expected_amount and r.expected_amount > 0:
                r.variance = r.total_amount - r.expected_amount
                r.variance_pct = (r.variance / r.expected_amount) * 100.0
                r.is_anomaly = abs(r.variance_pct) > threshold
            else:
                r.variance = 0.0
                r.variance_pct = 0.0
                r.is_anomaly = False

    # ---------- Actions ----------
    def action_recompute(self):
        for r in self:
            r._compute_expected()
            r._compute_variance()
        return True

    def action_confirm(self):
        for r in self:
            r.state = "anomaly" if r.is_anomaly else "confirmed"
        return True

    def action_reset_draft(self):
        self.write({"state": "draft"})
        return True

    @api.constrains("billing_month")
    def _check_month_first(self):
        for r in self:
            if r.billing_month and r.billing_month.day != 1:
                raise ValidationError(
                    "billing_month must be the first day of the month "
                    f"(got {r.billing_month}). Use the 1st."
                )
