"""Override of wms.daily.report from kob_wms:

* Filter all aggregations by company (cron iterates active companies).
* Replace HTML body with the same minimal card style used by the
  Dispatch Daily report (kob-dr-card).
* Append a per-round / per-batch breakdown table showing each
  dispatch round of the day with totals at the bottom.
"""

import json
import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


PLATFORM_ICONS = {
    "shopee": "🛒",
    "lazada": "🟦",
    "tiktok": "🎵",
    "odoo":   "🟣",
    "pos":    "🏬",
    "manual": "✍️",
}


class WmsDailyReport(models.Model):
    _inherit = "wms.daily.report"

    rounds_json = fields.Text(
        readonly=True,
        help="JSON cache of per-round breakdown used to render the card.",
    )

    # ------------------------------------------------------------------
    # Aggregation — company-scoped
    # ------------------------------------------------------------------

    def _compute_metrics(self, for_date):
        """Re-implements the parent metrics aggregation so every search
        is scoped to self.env.company (cron runs once per company)."""
        env = self.env
        company = env.company
        date_from = fields.Datetime.to_datetime(for_date)
        date_to = date_from + timedelta(days=1)

        SO = env["wms.sales.order"].sudo()
        base_domain = [
            ("create_date", ">=", date_from),
            ("create_date", "<", date_to),
            ("company_id", "=", company.id),
        ]
        orders = SO.search(base_domain)
        shipped = orders.filtered(lambda o: o.status == "shipped")
        cancelled = orders.filtered(lambda o: o.status == "cancelled")
        pending = orders.filtered(
            lambda o: o.status in ("pending", "picking", "picked", "packing")
        )

        def _count_platform(p):
            return len(orders.filtered(
                lambda o: getattr(o, "platform", None) == p
            ))

        sale_orders = orders.mapped("sale_order_id")
        try:
            total_qty = sum(
                line.qty_picked or 0
                for o in orders for line in getattr(o, "line_ids", [])
            )
        except Exception:
            total_qty = 0.0

        metrics = {
            "total_orders": len(orders),
            "shipped_orders": len(shipped),
            "cancelled_orders": len(cancelled),
            "pending_orders": len(pending),
            "shopee_orders": _count_platform("shopee"),
            "lazada_orders": _count_platform("lazada"),
            "tiktok_orders": _count_platform("tiktok"),
            "odoo_orders": _count_platform("odoo"),
            "total_value": sum(sale_orders.mapped("amount_total")),
            "total_qty": total_qty,
            "avg_pick_min": 0.0, "sla_pick_pct": 0.0,
            "avg_pack_min": 0.0, "sla_pack_pct": 0.0,
        }

        if "pick_duration_min" in SO._fields:
            pick_mins = [o.pick_duration_min for o in shipped
                         if o.pick_duration_min]
            if pick_mins:
                metrics["avg_pick_min"] = sum(pick_mins) / len(pick_mins)
                metrics["sla_pick_pct"] = (
                    sum(1 for m in pick_mins if m <= 120) / len(pick_mins) * 100
                )
        if "pack_duration_min" in SO._fields:
            pack_mins = [o.pack_duration_min for o in shipped
                         if o.pack_duration_min]
            if pack_mins:
                metrics["avg_pack_min"] = sum(pack_mins) / len(pack_mins)
                metrics["sla_pack_pct"] = (
                    sum(1 for m in pack_mins if m <= 60) / len(pack_mins) * 100
                )

        Defect = env.get("wms.quality.defect")
        if Defect is not None:
            d_domain = [
                ("report_date", ">=", date_from),
                ("report_date", "<", date_to),
            ]
            if "company_id" in Defect._fields:
                d_domain.append(("company_id", "=", company.id))
            metrics["defect_count"] = Defect.sudo().search_count(d_domain)
        else:
            metrics["defect_count"] = 0

        Expiry = env.get("wms.expiry.alert")
        if Expiry is not None:
            e_domain = [("alert_date", "=", for_date)]
            if "company_id" in Expiry._fields:
                e_domain.append(("company_id", "=", company.id))
            metrics["expiry_alert_count"] = Expiry.sudo().search_count(e_domain)
        else:
            metrics["expiry_alert_count"] = 0

        # Cache per-round breakdown for rendering
        metrics["rounds_json"] = json.dumps(
            self._compute_round_summary(for_date, company),
            ensure_ascii=False,
        )
        return metrics

    def _compute_round_summary(self, for_date, company):
        """For each dispatch round opened on `for_date` for `company`,
        return rows with totals per (platform, courier).
        Returns: [{round, label, opened, closed, state, batches: [...]}, ...]
        """
        Round = self.env.get("wms.dispatch.round")
        if Round is None:
            return []
        Round = Round.sudo()
        start = datetime.combine(for_date, time.min)
        end = start + timedelta(days=1)

        rounds = Round.search([
            ("company_id", "=", company.id),
            ("date_open", ">=", start),
            ("date_open", "<", end),
        ], order="date_open asc")

        out = []
        for r in rounds:
            batches = []
            for b in r.batch_ids.filtered(lambda x: x.state != "cancelled"):
                batches.append({
                    "name": b.name,
                    "platform": b.platform or "manual",
                    "courier": b.courier_id.name or "—",
                    "scans": b.scanned_count,
                    "state": b.state,
                })
            out.append({
                "name": r.name,
                "label": r.label or "",
                "opened": fields.Datetime.to_string(r.date_open),
                "closed": fields.Datetime.to_string(r.date_close) if r.date_close else "",
                "state": r.state,
                "batches": batches,
                "total_scans": sum(b["scans"] for b in batches),
                "total_batches": len(batches),
            })
        return out

    # ------------------------------------------------------------------
    # HTML — minimal card style
    # ------------------------------------------------------------------

    def _render_body_html(self, m, for_date):
        company = self.company_id or self.env.company
        rounds = []
        if m.get("rounds_json"):
            try:
                rounds = json.loads(m["rounds_json"])
            except Exception:
                rounds = []

        platform_rows = "".join(
            f"<tr>"
            f"<td class='kob-dr-platform'>{PLATFORM_ICONS.get(p, '📦')} {p.capitalize()}</td>"
            f"<td class='kob-dr-num'>{m.get(p+'_orders', 0)}</td>"
            f"</tr>"
            for p in ("shopee", "lazada", "tiktok", "odoo")
            if m.get(p + "_orders", 0)
        ) or (
            "<tr><td colspan='2' class='kob-dr-empty'>No platform activity.</td></tr>"
        )

        round_blocks = ""
        for r in rounds:
            batch_rows = "".join(
                f"<tr>"
                f"<td>{b['name']}</td>"
                f"<td class='kob-dr-platform'>"
                f"{PLATFORM_ICONS.get(b['platform'], '📦')} {b['platform'].capitalize()}</td>"
                f"<td>{b['courier']}</td>"
                f"<td class='kob-dr-num'>{b['scans']}</td>"
                f"<td><span class='kob-dr-pill kob-dr-pill--{b['state']}'>{b['state']}</span></td>"
                f"</tr>"
                for b in r["batches"]
            ) or (
                "<tr><td colspan='5' class='kob-dr-empty'>"
                "No batches opened in this round."
                "</td></tr>"
            )
            round_blocks += f"""
<div class="kob-dr-round">
  <div class="kob-dr-round-head">
    <span class="kob-dr-round-name">{r['name']}</span>
    <span class="kob-dr-round-label">{r['label']}</span>
    <span class="kob-dr-round-state kob-dr-pill kob-dr-pill--{r['state']}">{r['state']}</span>
    <span class="kob-dr-round-spacer"></span>
    <span class="kob-dr-round-totals">
      <b>{r['total_batches']}</b> batches · <b>{r['total_scans']}</b> scans
    </span>
  </div>
  <table class="kob-dr-table kob-dr-round-table">
    <thead>
      <tr>
        <th>Batch</th>
        <th>Platform</th>
        <th>Courier</th>
        <th class="kob-dr-num">Scans</th>
        <th>State</th>
      </tr>
    </thead>
    <tbody>{batch_rows}</tbody>
  </table>
</div>
"""

        rounds_section = round_blocks or (
            "<div class='kob-dr-empty kob-dr-empty--block'>"
            "No dispatch rounds opened on this day."
            "</div>"
        )

        # Grand totals across all rounds
        grand_batches = sum(r["total_batches"] for r in rounds)
        grand_scans = sum(r["total_scans"] for r in rounds)

        return f"""
<div class="kob-dr-card">
  <div class="kob-dr-head">
    <div class="kob-dr-title">📊 Daily WMS Report</div>
    <div class="kob-dr-subtitle">{company.name} · {for_date}</div>
  </div>
  <div class="kob-dr-totals">
    <div><span class="kob-dr-num-big">{m.get('total_orders', 0)}</span><span>Orders</span></div>
    <div><span class="kob-dr-num-big">{m.get('shipped_orders', 0)}</span><span>Shipped</span></div>
    <div><span class="kob-dr-num-big">{m.get('pending_orders', 0)}</span><span>Pending</span></div>
    <div><span class="kob-dr-num-big">{m.get('cancelled_orders', 0)}</span><span>Cancelled</span></div>
    <div><span class="kob-dr-num-big">฿{m.get('total_value', 0):,.0f}</span><span>Value</span></div>
  </div>

  <div class="kob-dr-section-title">Platform breakdown</div>
  <table class="kob-dr-table">
    <thead>
      <tr><th>Platform</th><th class="kob-dr-num">Orders</th></tr>
    </thead>
    <tbody>{platform_rows}</tbody>
  </table>

  <div class="kob-dr-section-title">
    Dispatch rounds
    <span class="kob-dr-section-totals">
      <b>{len(rounds)}</b> rounds · <b>{grand_batches}</b> batches · <b>{grand_scans}</b> scans
    </span>
  </div>
  {rounds_section}

  <div class="kob-dr-section-title">SLA &amp; Quality</div>
  <table class="kob-dr-table">
    <tbody>
      <tr><td>Avg Pick (min)</td><td class="kob-dr-num">{m.get('avg_pick_min', 0):.1f}</td>
          <td>SLA pass</td><td class="kob-dr-num">{m.get('sla_pick_pct', 0):.1f}%</td></tr>
      <tr><td>Avg Pack (min)</td><td class="kob-dr-num">{m.get('avg_pack_min', 0):.1f}</td>
          <td>SLA pass</td><td class="kob-dr-num">{m.get('sla_pack_pct', 0):.1f}%</td></tr>
      <tr><td>Defects</td><td class="kob-dr-num">{m.get('defect_count', 0)}</td>
          <td>Expiry alerts</td><td class="kob-dr-num">{m.get('expiry_alert_count', 0)}</td></tr>
    </tbody>
  </table>
</div>
""".strip()

    # ------------------------------------------------------------------
    # Cron — iterate every company so each gets its own record
    # ------------------------------------------------------------------

    @api.model
    def cron_generate_daily_report(self):
        today = fields.Date.context_today(self)
        yesterday = today - timedelta(days=1)
        for company in self.env["res.company"].sudo().search([]):
            try:
                self.with_company(company)._build_for_company(yesterday, company)
            except Exception:
                _logger.exception(
                    "Daily report failed for company %s", company.name
                )

    def _build_for_company(self, for_date, company):
        existing = self.sudo().search([
            ("report_date", "=", for_date),
            ("company_id", "=", company.id),
        ], limit=1)
        if existing:
            return existing
        metrics = self.with_company(company)._compute_metrics(for_date)
        body = self.with_company(company)._render_body_html(metrics, for_date)
        report = self.sudo().with_company(company).create({
            "report_date": for_date,
            "company_id": company.id,
            "body_html": body,
            **metrics,
        })
        report._notify_recipients(body, for_date)
        return report

    def action_regenerate(self):
        for r in self:
            metrics = r.with_company(r.company_id)._compute_metrics(r.report_date)
            body = r.with_company(r.company_id)._render_body_html(metrics, r.report_date)
            r.write({"body_html": body, **metrics})
        return True
