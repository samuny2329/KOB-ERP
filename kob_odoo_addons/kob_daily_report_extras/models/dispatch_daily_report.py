"""End-of-day Outbound/Dispatch summary.

Aggregates scan items + batches per dispatch round closed (or still open)
on the report date, breaks them down by platform × courier, and posts a
minimal Adaptive Card to a configured MS Teams webhook.
"""

import json
import logging
from datetime import datetime, time, timedelta
from urllib import request as urllib_request, error as urllib_error

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


PARAM_WEBHOOK = "kob_daily_report_extras.teams_webhook"
PLATFORM_ICONS = {
    "shopee": "🛒",
    "lazada": "🟦",
    "tiktok": "🎵",
    "odoo": "🟣",
    "pos": "🏬",
    "manual": "✍️",
}


class DispatchDailyReport(models.Model):
    _name = "wms.dispatch.daily.report"
    _description = "Outbound / Dispatch Daily Report"
    _inherit = ["mail.thread"]
    _order = "report_date desc, company_id"
    _rec_name = "display_name"

    report_date = fields.Date(
        required=True, default=fields.Date.context_today, index=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True,
        default=lambda s: s.env.company, index=True,
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    round_count = fields.Integer(readonly=True)
    batch_count = fields.Integer(readonly=True)
    scan_count = fields.Integer(readonly=True)
    dispatched_batch_count = fields.Integer(readonly=True)
    pending_scan_count = fields.Integer(
        readonly=True,
        help="Scans still in scanning batches at end of day.",
    )

    breakdown_json = fields.Text(
        readonly=True,
        help=(
            "JSON: list of {platform, courier, scans, batches, "
            "dispatched_batches} rows used to render the card."
        ),
    )
    body_html = fields.Html(readonly=True)
    teams_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("sent", "Sent to Teams"),
            ("skipped", "Skipped (no webhook)"),
            ("error", "Error"),
        ],
        default="pending", readonly=True, tracking=True,
    )
    teams_error = fields.Char(readonly=True)
    posted_to_discuss = fields.Boolean(readonly=True)

    _sql_constraints = [
        (
            "unique_per_day_company",
            "unique(report_date, company_id)",
            "One dispatch report per company per day.",
        ),
    ]

    @api.depends("report_date", "company_id")
    def _compute_display_name(self):
        for r in self:
            r.display_name = f"Dispatch {r.report_date} · {r.company_id.name or ''}".strip()

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _date_window(self, for_date):
        """Return (datetime_start, datetime_end) bracketing the report day
        in UTC. Treats dates as full-day slices for simplicity."""
        start = datetime.combine(for_date, time.min)
        end = start + timedelta(days=1)
        return start, end

    def _compute_metrics(self, for_date, company):
        Round = self.env["wms.dispatch.round"].sudo()
        Batch = self.env["wms.courier.batch"].sudo()
        ScanItem = self.env["wms.scan.item"].sudo()

        start_dt, end_dt = self._date_window(for_date)

        # Rounds opened today (including any still open at EOD)
        rounds = Round.search([
            ("company_id", "=", company.id),
            ("date_open", ">=", start_dt),
            ("date_open", "<", end_dt),
        ])

        # Batches that belong to those rounds OR were created today even
        # without a round (defensive)
        batches = Batch.search([
            ("company_id", "=", company.id),
            "|",
            ("dispatch_round_id", "in", rounds.ids),
            ("create_date", ">=", start_dt),
            ("create_date", "<", end_dt),
        ])
        # Filter actual scans created today for accurate counts
        scans = ScanItem.search([
            ("company_id", "=", company.id),
            ("scanned_at", ">=", start_dt),
            ("scanned_at", "<", end_dt),
        ])

        dispatched = batches.filtered(lambda b: b.state == "dispatched")
        pending_scans = scans.filtered(
            lambda s: s.batch_id and s.batch_id.state == "scanning"
        )

        # Group by (platform, courier)
        groups = {}
        for b in batches:
            if b.state == "cancelled":
                continue
            key = (b.platform or "manual", b.courier_id.name or "—")
            row = groups.setdefault(key, {
                "platform": key[0],
                "courier": key[1],
                "scans": 0,
                "batches": 0,
                "dispatched_batches": 0,
            })
            row["scans"] += b.scanned_count
            row["batches"] += 1
            if b.state == "dispatched":
                row["dispatched_batches"] += 1
        breakdown = sorted(
            groups.values(),
            key=lambda r: (r["platform"], r["courier"]),
        )

        return {
            "round_count": len(rounds),
            "batch_count": len(batches.filtered(lambda b: b.state != "cancelled")),
            "scan_count": len(scans),
            "dispatched_batch_count": len(dispatched),
            "pending_scan_count": len(pending_scans),
            "breakdown_json": json.dumps(breakdown, ensure_ascii=False),
        }

    # ------------------------------------------------------------------
    # HTML rendering — minimal account-style card (Discuss + form view)
    # ------------------------------------------------------------------

    def _render_body_html(self, breakdown, totals, for_date, company):
        rows = "".join(
            f"<tr>"
            f"<td class='kob-dr-platform'>"
            f"{PLATFORM_ICONS.get(r['platform'], '📦')} {r['platform'].capitalize()}"
            f"</td>"
            f"<td>{r['courier']}</td>"
            f"<td class='kob-dr-num'>{r['scans']}</td>"
            f"<td class='kob-dr-num'>{r['batches']}</td>"
            f"<td class='kob-dr-num'>{r['dispatched_batches']}</td>"
            f"</tr>"
            for r in breakdown
        ) or (
            "<tr><td colspan='5' class='kob-dr-empty'>"
            "No dispatch activity for this day."
            "</td></tr>"
        )
        return f"""
<div class="kob-dr-card">
  <div class="kob-dr-head">
    <div class="kob-dr-title">📦 Dispatch Daily Report</div>
    <div class="kob-dr-subtitle">{company.name} · {for_date}</div>
  </div>
  <div class="kob-dr-totals">
    <div><span class="kob-dr-num-big">{totals['round_count']}</span><span>Rounds</span></div>
    <div><span class="kob-dr-num-big">{totals['batch_count']}</span><span>Batches</span></div>
    <div><span class="kob-dr-num-big">{totals['scan_count']}</span><span>Scans</span></div>
    <div><span class="kob-dr-num-big">{totals['dispatched_batch_count']}</span><span>Dispatched</span></div>
    <div><span class="kob-dr-num-big">{totals['pending_scan_count']}</span><span>Pending</span></div>
  </div>
  <table class="kob-dr-table">
    <thead>
      <tr>
        <th>Platform</th>
        <th>Courier</th>
        <th class="kob-dr-num">Scans</th>
        <th class="kob-dr-num">Batches</th>
        <th class="kob-dr-num">Dispatched</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>
""".strip()

    # ------------------------------------------------------------------
    # Teams Adaptive Card
    # ------------------------------------------------------------------

    def _build_teams_card(self, breakdown, totals, for_date, company):
        """Build an Adaptive Card v1.4 payload accepted by Teams incoming
        webhooks (wrapped in attachments[])."""
        # Header facts
        header_facts = [
            {"title": "Rounds", "value": str(totals["round_count"])},
            {"title": "Batches", "value": str(totals["batch_count"])},
            {"title": "Scans", "value": str(totals["scan_count"])},
            {"title": "Dispatched", "value": str(totals["dispatched_batch_count"])},
            {"title": "Pending", "value": str(totals["pending_scan_count"])},
        ]
        # Breakdown table — render as ColumnSet rows
        if breakdown:
            head = {
                "type": "ColumnSet",
                "spacing": "Medium",
                "separator": True,
                "columns": [
                    {"type": "Column", "width": "stretch",
                     "items": [{"type": "TextBlock", "text": "Platform",
                                "weight": "Bolder", "size": "Small",
                                "color": "Accent"}]},
                    {"type": "Column", "width": "stretch",
                     "items": [{"type": "TextBlock", "text": "Courier",
                                "weight": "Bolder", "size": "Small",
                                "color": "Accent"}]},
                    {"type": "Column", "width": "auto",
                     "items": [{"type": "TextBlock", "text": "Scans",
                                "weight": "Bolder", "size": "Small",
                                "color": "Accent",
                                "horizontalAlignment": "Right"}]},
                    {"type": "Column", "width": "auto",
                     "items": [{"type": "TextBlock", "text": "Batches",
                                "weight": "Bolder", "size": "Small",
                                "color": "Accent",
                                "horizontalAlignment": "Right"}]},
                ],
            }
            rows = [head]
            for r in breakdown:
                rows.append({
                    "type": "ColumnSet",
                    "columns": [
                        {"type": "Column", "width": "stretch",
                         "items": [{"type": "TextBlock",
                                    "text": f"{PLATFORM_ICONS.get(r['platform'], '📦')} {r['platform'].capitalize()}",
                                    "size": "Small", "wrap": True}]},
                        {"type": "Column", "width": "stretch",
                         "items": [{"type": "TextBlock",
                                    "text": r["courier"],
                                    "size": "Small", "wrap": True,
                                    "isSubtle": True}]},
                        {"type": "Column", "width": "auto",
                         "items": [{"type": "TextBlock",
                                    "text": str(r["scans"]),
                                    "size": "Small",
                                    "horizontalAlignment": "Right"}]},
                        {"type": "Column", "width": "auto",
                         "items": [{"type": "TextBlock",
                                    "text": str(r["batches"]),
                                    "size": "Small",
                                    "horizontalAlignment": "Right"}]},
                    ],
                })
            breakdown_block = rows
        else:
            breakdown_block = [{
                "type": "TextBlock",
                "text": "No dispatch activity for this day.",
                "isSubtle": True, "size": "Small",
                "horizontalAlignment": "Center", "spacing": "Large",
            }]

        body = [
            {"type": "TextBlock",
             "text": "📦 Dispatch Daily Report",
             "weight": "Bolder", "size": "Large", "wrap": True},
            {"type": "TextBlock",
             "text": f"{company.name} · {for_date}",
             "isSubtle": True, "size": "Small", "spacing": "None",
             "wrap": True},
            {"type": "FactSet", "facts": header_facts, "spacing": "Medium"},
            *breakdown_block,
        ]

        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": body,
        }
        return {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }],
        }

    def _post_to_teams(self, payload):
        """POST the Adaptive Card payload to the configured webhook."""
        url = self.env["ir.config_parameter"].sudo().get_param(PARAM_WEBHOOK)
        if not url:
            return ("skipped", "No webhook configured")
        data = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=15) as resp:
                code = resp.getcode()
                if 200 <= code < 300:
                    return ("sent", "")
                return ("error", f"HTTP {code}")
        except urllib_error.HTTPError as e:
            return ("error", f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            return ("error", str(e)[:240])

    # ------------------------------------------------------------------
    # Build + send
    # ------------------------------------------------------------------

    def _build_and_send(self, for_date, company):
        existing = self.sudo().search([
            ("report_date", "=", for_date),
            ("company_id", "=", company.id),
        ], limit=1)
        if existing:
            existing.action_regenerate()
            return existing

        metrics = self._compute_metrics(for_date, company)
        breakdown = json.loads(metrics["breakdown_json"])
        body = self._render_body_html(breakdown, metrics, for_date, company)

        rec = self.sudo().with_company(company).create({
            "report_date": for_date,
            "company_id": company.id,
            "body_html": body,
            **metrics,
        })

        # Send to Teams
        payload = self._build_teams_card(breakdown, metrics, for_date, company)
        status, err = self._post_to_teams(payload)
        rec.write({
            "teams_status": status,
            "teams_error": err if err else False,
        })

        # Mirror to Discuss as a backup so people without Teams still see it
        try:
            rec.message_post(
                body=body,
                subject=f"📦 Dispatch Daily Report — {for_date}",
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            rec.posted_to_discuss = True
        except Exception:
            _logger.exception("Failed posting daily dispatch to Discuss")

        return rec

    @api.model
    def cron_send_today(self):
        today = fields.Date.context_today(self)
        for company in self.env["res.company"].sudo().search([]):
            try:
                self.with_company(company)._build_and_send(today, company)
            except Exception:
                _logger.exception(
                    "cron_send_today failed for company %s", company.name
                )

    def action_regenerate(self):
        for r in self:
            metrics = self._compute_metrics(r.report_date, r.company_id)
            breakdown = json.loads(metrics["breakdown_json"])
            body = self._render_body_html(
                breakdown, metrics, r.report_date, r.company_id,
            )
            r.write({"body_html": body, **metrics})

    def action_resend_teams(self):
        for r in self:
            breakdown = json.loads(r.breakdown_json or "[]")
            metrics = {
                "round_count": r.round_count,
                "batch_count": r.batch_count,
                "scan_count": r.scan_count,
                "dispatched_batch_count": r.dispatched_batch_count,
                "pending_scan_count": r.pending_scan_count,
            }
            payload = r._build_teams_card(
                breakdown, metrics, r.report_date, r.company_id,
            )
            status, err = r._post_to_teams(payload)
            r.write({
                "teams_status": status,
                "teams_error": err if err else False,
            })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Resend"),
                "message": _("Reports re-sent. Check teams_status."),
                "type": "info",
                "sticky": False,
            },
        }
