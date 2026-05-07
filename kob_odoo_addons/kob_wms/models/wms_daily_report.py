"""WMS Daily Sales Report — automate "สร้าง Daily Sales Report"
(P1 Critical from Audit). Replaces "รวม data จากหลาย source ใน Excel
แล้วส่ง LINE/Email" manual process.

Cron runs at 07:00 daily → creates a wms.daily.report record for
yesterday, computes sales + fulfilment metrics, and emails it to all
active supervisors + managers.
"""
from datetime import timedelta

from markupsafe import Markup

from odoo import models, fields, api, _


class WmsDailyReport(models.Model):
    _name = 'wms.daily.report'
    _description = 'WMS Daily Sales & Fulfilment Report'
    _inherit = ['mail.thread']
    _order = 'report_date desc'
    _rec_name = 'report_date'

    report_date = fields.Date(string='Report Date', required=True,
                              default=fields.Date.context_today)
    # Order metrics (from wms.sales.order)
    total_orders = fields.Integer(readonly=True)
    shipped_orders = fields.Integer(readonly=True)
    cancelled_orders = fields.Integer(readonly=True)
    pending_orders = fields.Integer(readonly=True)

    total_qty = fields.Float(readonly=True, digits=(12, 2))
    total_value = fields.Float(readonly=True, digits=(14, 2))

    # Platform breakdown
    shopee_orders = fields.Integer(readonly=True)
    lazada_orders = fields.Integer(readonly=True)
    tiktok_orders = fields.Integer(readonly=True)
    odoo_orders = fields.Integer(readonly=True)

    # SLA metrics
    avg_pick_min = fields.Float(readonly=True, digits=(10, 2))
    avg_pack_min = fields.Float(readonly=True, digits=(10, 2))
    sla_pick_pct = fields.Float(readonly=True, digits=(5, 2))
    sla_pack_pct = fields.Float(readonly=True, digits=(5, 2))

    # Quality metrics
    defect_count = fields.Integer(readonly=True)
    expiry_alert_count = fields.Integer(readonly=True)

    body_html = fields.Html(readonly=True, sanitize=False)
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)

    _sql_constraints = [
        ('report_date_company_unique',
         'unique(report_date, company_id)',
         'Only one daily report per day per company.'),
    ]

    # ────────────────────────────────────────────────────────────────────
    # Compute report metrics for a date
    # ────────────────────────────────────────────────────────────────────
    def _compute_metrics(self, for_date):
        env = self.env
        date_from = fields.Datetime.to_datetime(for_date)
        date_to = date_from + timedelta(days=1)

        SO = env['wms.sales.order'].sudo()
        base_domain = [
            ('create_date', '>=', date_from),
            ('create_date', '<', date_to),
        ]
        orders = SO.search(base_domain)
        shipped = orders.filtered(lambda o: o.status == 'shipped')
        cancelled = orders.filtered(lambda o: o.status == 'cancelled')
        pending = orders.filtered(
            lambda o: o.status in ('pending', 'picking', 'picked', 'packing'))

        def _count_platform(platform):
            return len(orders.filtered(
                lambda o: getattr(o, 'platform', None) == platform))

        metrics = {
            'total_orders': len(orders),
            'shipped_orders': len(shipped),
            'cancelled_orders': len(cancelled),
            'pending_orders': len(pending),
            'shopee_orders': _count_platform('shopee'),
            'lazada_orders': _count_platform('lazada'),
            'tiktok_orders': _count_platform('tiktok'),
            'odoo_orders': _count_platform('odoo'),
        }

        # Value & qty
        sale_orders = orders.mapped('sale_order_id')
        metrics['total_value'] = sum(sale_orders.mapped('amount_total'))
        try:
            metrics['total_qty'] = sum(
                line.qty_picked or 0
                for o in orders for line in getattr(o, 'line_ids', [])
            )
        except Exception:
            metrics['total_qty'] = 0.0

        # SLA (if fields exist)
        if 'pick_duration_min' in SO._fields:
            pick_mins = [o.pick_duration_min for o in shipped
                         if o.pick_duration_min]
            metrics['avg_pick_min'] = (
                sum(pick_mins) / len(pick_mins)) if pick_mins else 0
            compliant_pick = sum(1 for m in pick_mins if m <= 120)
            metrics['sla_pick_pct'] = (
                compliant_pick / len(pick_mins) * 100) if pick_mins else 0
        if 'pack_duration_min' in SO._fields:
            pack_mins = [o.pack_duration_min for o in shipped
                         if o.pack_duration_min]
            metrics['avg_pack_min'] = (
                sum(pack_mins) / len(pack_mins)) if pack_mins else 0
            compliant_pack = sum(1 for m in pack_mins if m <= 60)
            metrics['sla_pack_pct'] = (
                compliant_pack / len(pack_mins) * 100) if pack_mins else 0

        # Quality
        metrics['defect_count'] = env['wms.quality.defect'].sudo().search_count([
            ('report_date', '>=', date_from),
            ('report_date', '<', date_to),
        ])
        metrics['expiry_alert_count'] = env['wms.expiry.alert'].sudo().search_count([
            ('alert_date', '=', for_date),
        ])

        return metrics

    # ──────────────────────────────────────────────────────────────────
    # HTML rendering — Odoo 19 native table style, embedded inline so the
    # form-view <field widget="html"> renders consistently and Discuss /
    # email recipients see the same card-style report.
    # ──────────────────────────────────────────────────────────────────
    _DAILY_INLINE_CSS = """
<style>
.kob-rpt {
  font-family: "Inter","Roboto","Segoe UI",-apple-system,"Helvetica Neue",Arial,"Noto Sans Thai",sans-serif;
  font-size: 13px; color: #2c2c2c; max-width: 920px; margin: 0;
}
.kob-rpt__header {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 14px 18px; background: linear-gradient(135deg,#714B67 0%,#5d3a55 100%);
  color: #fff; border-radius: 6px 6px 0 0; margin: 0;
}
.kob-rpt__title { font-size: 16px; font-weight: 700; margin: 0; }
.kob-rpt__date  { font-size: 12px; opacity: 0.85; font-variant-numeric: tabular-nums; }
.kob-rpt__section {
  border: 1px solid #e0e0e0; border-top: 0;
  background: #fff;
}
.kob-rpt__section:last-of-type { border-radius: 0 0 6px 6px; }
.kob-rpt__section-title {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 18px; background: #f6f6f6;
  border-bottom: 1px solid #e0e0e0;
  font-size: 11px; font-weight: 700; color: #6c757d;
  text-transform: uppercase; letter-spacing: 0.6px;
}
.kob-rpt__section-icon { font-size: 14px; }
.kob-rpt table {
  width: 100%; border-collapse: separate; border-spacing: 0;
  margin: 0; font-size: 13px;
}
.kob-rpt table th, .kob-rpt table td {
  padding: 10px 18px; vertical-align: middle;
}
.kob-rpt table th {
  text-align: left; font-weight: 600; color: #6c757d;
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px;
  background: #fafafa; border-bottom: 1px solid #f0f0f0;
}
.kob-rpt table th.kob-rpt-num { text-align: right; }
.kob-rpt table td { border-bottom: 1px solid #f0f0f0; color: #2c2c2c; }
.kob-rpt table td.kob-rpt-label { color: #6c757d; font-weight: 500; width: 40%; }
.kob-rpt table td.kob-rpt-num {
  text-align: right; font-variant-numeric: tabular-nums;
  font-weight: 600; white-space: nowrap;
}
.kob-rpt table tr:last-child td { border-bottom: 0; }
.kob-rpt table tr:nth-child(even) td { background: rgba(246,246,246,0.4); }
.kob-rpt__pill {
  display: inline-block; padding: 2px 9px; border-radius: 11px;
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.4px;
  text-transform: uppercase; line-height: 1.5;
}
.kob-rpt__pill--ok    { background: #e6f4ea; color: #137333; }
.kob-rpt__pill--warn  { background: #fef7e0; color: #b06000; }
.kob-rpt__pill--bad   { background: #fce8e6; color: #c5221f; }
.kob-rpt__pill--info  { background: #e8f0fe; color: #1a73e8; }
.kob-rpt__bar {
  display: inline-block; width: 80px; height: 6px;
  background: #f0f0f0; border-radius: 3px; overflow: hidden;
  vertical-align: middle; margin-right: 8px;
}
.kob-rpt__bar-fill {
  height: 100%;
  background: linear-gradient(90deg,#714B67 0%,#5d3a55 100%);
}
.kob-rpt__footer {
  padding: 9px 18px; font-size: 11px; color: #adb5bd;
  text-align: right; background: #fafafa;
  border: 1px solid #e0e0e0; border-top: 0;
  border-radius: 0 0 6px 6px;
}
</style>
"""

    @staticmethod
    def _sla_pill(pct):
        """Return a coloured pill class based on SLA pass percentage."""
        if pct >= 90:
            return "kob-rpt__pill--ok"
        if pct >= 70:
            return "kob-rpt__pill--warn"
        return "kob-rpt__pill--bad"

    @staticmethod
    def _sla_bar(pct):
        clamped = max(0, min(100, pct))
        return (
            f'<span class="kob-rpt__bar">'
            f'<span class="kob-rpt__bar-fill" '
            f'style="width:{clamped:.0f}%"></span></span>'
        )

    def _render_body_html(self, m, for_date):
        """Render the daily report as a card with Odoo 19-styled tables.

        Sections: Order Summary · Platform Breakdown · SLA Compliance · Quality.
        Numbers are right-aligned with tabular-nums.  Each section is its
        own subtable so Discuss / email render consistently.
        """
        total = m.get('total_orders') or 0
        shipped = m.get('shipped_orders') or 0
        pending = m.get('pending_orders') or 0
        cancelled = m.get('cancelled_orders') or 0
        ship_pct = (shipped / total * 100) if total else 0
        sla_pick = m.get('sla_pick_pct') or 0
        sla_pack = m.get('sla_pack_pct') or 0

        # ── Order Summary table ───────────────────────────────────────
        order_rows = [
            ('<b>Total Orders</b>', f"{total:,}"),
            ('✅ Shipped',
             f"{shipped:,} <span class='kob-rpt__pill kob-rpt__pill--info'>"
             f"{ship_pct:.0f}%</span>"),
            ('⏳ Pending',  f"{pending:,}"),
            ('❌ Cancelled', f"{cancelled:,}"),
            ('<b>Total Value</b>',
             f"<b>฿{m.get('total_value', 0):,.2f}</b>"),
        ]
        order_html = "".join(
            f"<tr><td class='kob-rpt-label'>{lbl}</td>"
            f"<td class='kob-rpt-num'>{val}</td></tr>"
            for lbl, val in order_rows
        )

        # ── Platform breakdown table ──────────────────────────────────
        platforms = [
            ('🛒 Shopee',  m.get('shopee_orders') or 0),
            ('🟦 Lazada',  m.get('lazada_orders') or 0),
            ('🎵 TikTok',  m.get('tiktok_orders') or 0),
            ('🟣 Odoo',    m.get('odoo_orders')   or 0),
        ]
        plat_total = sum(v for _l, v in platforms) or 1
        plat_html = "".join(
            f"<tr><td class='kob-rpt-label'>{lbl}</td>"
            f"<td class='kob-rpt-num'>{v:,}</td>"
            f"<td class='kob-rpt-num' style='width:140px'>"
            f"{self._sla_bar(v / plat_total * 100)}"
            f"<span style='color:#6c757d;font-size:11px'>"
            f"{v / plat_total * 100:.0f}%</span></td></tr>"
            for lbl, v in platforms
        )

        # ── SLA Compliance table ──────────────────────────────────────
        sla_rows = [
            ('Pick (F1)', m.get('avg_pick_min') or 0, sla_pick),
            ('Pack (F2)', m.get('avg_pack_min') or 0, sla_pack),
        ]
        sla_html = "".join(
            f"<tr><td class='kob-rpt-label'>{stage}</td>"
            f"<td class='kob-rpt-num'>{avg:.1f} min</td>"
            f"<td class='kob-rpt-num'>"
            f"<span class='kob-rpt__pill {self._sla_pill(pct)}'>"
            f"{pct:.1f}%</span></td></tr>"
            for stage, avg, pct in sla_rows
        )

        # ── Quality table ─────────────────────────────────────────────
        defect = m.get('defect_count') or 0
        expiry = m.get('expiry_alert_count') or 0
        qual_html = (
            f"<tr><td class='kob-rpt-label'>🐛 Defects reported</td>"
            f"<td class='kob-rpt-num'>"
            f"<span class='kob-rpt__pill "
            f"{'kob-rpt__pill--ok' if defect == 0 else 'kob-rpt__pill--bad'}'>"
            f"{defect:,}</span></td></tr>"
            f"<tr><td class='kob-rpt-label'>⏰ Expiry alerts</td>"
            f"<td class='kob-rpt-num'>"
            f"<span class='kob-rpt__pill "
            f"{'kob-rpt__pill--ok' if expiry == 0 else 'kob-rpt__pill--warn'}'>"
            f"{expiry:,}</span></td></tr>"
        )

        return self._DAILY_INLINE_CSS + (
            "<div class='kob-rpt'>"
            "<div class='kob-rpt__header'>"
            "<div class='kob-rpt__title'>📊 Daily WMS Report</div>"
            f"<div class='kob-rpt__date'>{for_date}</div>"
            "</div>"

            "<div class='kob-rpt__section'>"
            "<div class='kob-rpt__section-title'>"
            "<span class='kob-rpt__section-icon'>📦</span>"
            "Order Summary</div>"
            f"<table>{order_html}</table>"
            "</div>"

            "<div class='kob-rpt__section'>"
            "<div class='kob-rpt__section-title'>"
            "<span class='kob-rpt__section-icon'>🌐</span>"
            "Platform Breakdown</div>"
            "<table><thead><tr>"
            "<th>Platform</th>"
            "<th class='kob-rpt-num'>Orders</th>"
            "<th class='kob-rpt-num'>Share</th>"
            "</tr></thead>"
            f"<tbody>{plat_html}</tbody></table>"
            "</div>"

            "<div class='kob-rpt__section'>"
            "<div class='kob-rpt__section-title'>"
            "<span class='kob-rpt__section-icon'>⏱️</span>"
            "SLA Compliance</div>"
            "<table><thead><tr>"
            "<th>Stage</th>"
            "<th class='kob-rpt-num'>Avg Time</th>"
            "<th class='kob-rpt-num'>SLA Pass</th>"
            "</tr></thead>"
            f"<tbody>{sla_html}</tbody></table>"
            "</div>"

            "<div class='kob-rpt__section'>"
            "<div class='kob-rpt__section-title'>"
            "<span class='kob-rpt__section-icon'>🎯</span>"
            "Quality</div>"
            f"<table>{qual_html}</table>"
            "</div>"

            "<div class='kob-rpt__footer'>"
            "Auto-generated by KOB WMS · Daily Sales Report Cron"
            "</div>"
            "</div>"
        )

    # ────────────────────────────────────────────────────────────────────
    # Cron: generate yesterday's report at 07:00
    # ────────────────────────────────────────────────────────────────────
    @api.model
    def cron_generate_daily_report(self):
        today = fields.Date.context_today(self)
        yesterday = today - timedelta(days=1)

        existing = self.sudo().search([('report_date', '=', yesterday)], limit=1)
        if existing:
            return existing

        metrics = self._compute_metrics(yesterday)
        body = self._render_body_html(metrics, yesterday)

        report = self.sudo().create({
            'report_date': yesterday,
            'body_html': body,
            **metrics,
        })

        # Email to supervisors + managers
        report._notify_recipients(body, yesterday)
        return report

    def _notify_recipients(self, body, for_date):
        recipient_groups = [
            self.env.ref('kob_wms.group_wms_supervisor',
                         raise_if_not_found=False),
            self.env.ref('kob_wms.group_wms_manager',
                         raise_if_not_found=False),
        ]
        recipient_ids = set()
        for g in recipient_groups:
            if g:
                # Odoo 19 renamed res.groups.users -> all_user_ids
                # (includes indirect members via implied_ids).
                # Fall back to user_ids if all_user_ids is unavailable.
                users = g.all_user_ids if "all_user_ids" in g._fields else g.user_ids
                for user in users:
                    if user.partner_id:
                        recipient_ids.add(user.partner_id.id)
        if not recipient_ids:
            return

        self.ensure_one()
        # Wrap with Markup so Odoo trusts the HTML and renders it instead
        # of escaping it to literal "<h2>...</h2>" text in chatter.
        self.message_post(
            body=Markup(body),
            subject=_('📊 Daily WMS Report — %s') % for_date,
            partner_ids=list(recipient_ids),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    def action_regenerate(self):
        """Manual regeneration button."""
        self.ensure_one()
        metrics = self._compute_metrics(self.report_date)
        self.write({
            'body_html': self._render_body_html(metrics, self.report_date),
            **metrics,
        })
        return True
