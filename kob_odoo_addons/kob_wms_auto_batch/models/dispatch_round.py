from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WmsDispatchRound(models.Model):
    """A dispatch round = a working session in which scan-Out events are
    grouped. Only one round per company is OPEN at a time; new scans
    auto-join the open round, and closing it forces the next scan to
    start a fresh round."""

    _name = "wms.dispatch.round"
    _description = "WMS Dispatch Round / Wave"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_open desc, id desc"

    name = fields.Char(
        required=True, copy=False, readonly=True,
        default=lambda s: _("New"),
    )
    label = fields.Char(
        help="Human-friendly label, e.g. 'Morning' or 'Round 1'.",
    )
    date_open = fields.Datetime(
        required=True, default=fields.Datetime.now, tracking=True,
    )
    date_close = fields.Datetime(readonly=True, tracking=True)
    state = fields.Selection(
        [("open", "Open"), ("closed", "Closed")],
        default="open", required=True, tracking=True, index=True,
    )
    batch_ids = fields.One2many(
        "wms.courier.batch", "dispatch_round_id", string="Batches",
    )
    batch_count = fields.Integer(compute="_compute_counts", store=True)
    scan_item_count = fields.Integer(compute="_compute_counts", store=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, required=True,
    )
    notes = fields.Text()

    _sql_constraints = [
        # We want only one open round per company. Use a partial index.
        # Implemented at app level too via _check_single_open.
    ]

    open_batch_count = fields.Integer(compute="_compute_counts", store=True)
    dispatched_batch_count = fields.Integer(compute="_compute_counts", store=True)
    total_expected = fields.Integer(compute="_compute_counts", store=True)
    total_scanned = fields.Integer(compute="_compute_counts", store=True)
    total_pending = fields.Integer(compute="_compute_counts", store=True)
    completion_pct = fields.Float(
        compute="_compute_counts", store=True, digits=(5, 1),
    )
    is_complete = fields.Boolean(
        compute="_compute_counts", store=True,
        help="True when every (non-cancelled) batch has been dispatched.",
    )
    breakdown_html = fields.Html(
        compute="_compute_breakdown_html",
        sanitize=False, readonly=True,
    )

    @api.depends(
        "batch_ids", "batch_ids.scanned_count", "batch_ids.state",
        "batch_ids.expected_count", "batch_ids.scanned_done_count",
        "batch_ids.pending_count",
    )
    def _compute_counts(self):
        for r in self:
            non_cx = r.batch_ids.filtered(lambda b: b.state != "cancelled")
            r.batch_count = len(r.batch_ids)
            r.scan_item_count = sum(b.scanned_count for b in r.batch_ids)
            r.open_batch_count = len(non_cx.filtered(lambda b: b.state == "scanning"))
            r.dispatched_batch_count = len(non_cx.filtered(lambda b: b.state == "dispatched"))
            exp = sum(non_cx.mapped("expected_count"))
            done = sum(non_cx.mapped("scanned_done_count"))
            r.total_expected = exp
            r.total_scanned = done
            r.total_pending = max(0, exp - done)
            r.completion_pct = (done / exp * 100) if exp else 0.0
            # Round complete = at least one batch AND all non-cancelled
            # batches are dispatched.
            r.is_complete = bool(non_cx) and all(
                b.state == "dispatched" for b in non_cx
            )

    @api.depends(
        "batch_ids", "batch_ids.scanned_count", "batch_ids.platform",
        "batch_ids.courier_id", "batch_ids.state",
        "batch_ids.expected_count", "batch_ids.scanned_done_count",
    )
    def _compute_breakdown_html(self):
        """Render a per-(platform, courier) breakdown table used on the
        round form to answer 'how many remaining per platform'."""
        platform_icons = {
            "shopee": "🛒", "lazada": "🟦", "tiktok": "🎵",
            "odoo": "🟣", "pos": "🏬", "manual": "✍️",
        }
        for r in self:
            rows = []
            grand_exp = grand_done = grand_pending = 0
            non_cx = r.batch_ids.filtered(lambda b: b.state != "cancelled")
            # Group by (platform, courier)
            groups = {}
            for b in non_cx:
                key = (b.platform or "manual", b.courier_id.name or "—")
                row = groups.setdefault(key, {
                    "expected": 0, "scanned": 0, "pending": 0,
                    "batches": 0, "states": [],
                })
                row["expected"] += b.expected_count
                row["scanned"] += b.scanned_done_count
                row["pending"] += b.pending_count
                row["batches"] += 1
                row["states"].append(b.state)
            for (platform, courier), v in sorted(groups.items()):
                grand_exp += v["expected"]
                grand_done += v["scanned"]
                grand_pending += v["pending"]
                pct = (v["scanned"] / v["expected"] * 100) if v["expected"] else 0
                done = all(s == "dispatched" for s in v["states"])
                state_pill = "✓ done" if done else f"⏳ {v['pending']} pending"
                state_class = "kob-dr-pill--dispatched" if done else "kob-dr-pill--scanning"
                bar_w = int(pct)
                rows.append(
                    f"<tr>"
                    f"<td class='kob-dr-platform'>{platform_icons.get(platform, '📦')} {platform.capitalize()}</td>"
                    f"<td>{courier}</td>"
                    f"<td class='kob-dr-num'>{v['batches']}</td>"
                    f"<td class='kob-dr-num'>{v['expected']}</td>"
                    f"<td class='kob-dr-num'>{v['scanned']}</td>"
                    f"<td class='kob-dr-num'><b>{v['pending']}</b></td>"
                    f"<td>"
                    f"<div class='kob-dr-bar'><div class='kob-dr-bar-fill' style='width:{bar_w}%'></div></div>"
                    f"<span class='kob-dr-bar-pct'>{pct:.0f}%</span>"
                    f"</td>"
                    f"<td><span class='kob-dr-pill {state_class}'>{state_pill}</span></td>"
                    f"</tr>"
                )
            if not rows:
                table = (
                    "<div class='kob-dr-empty--block'>"
                    "No active batches in this round yet."
                    "</div>"
                )
            else:
                grand_pct = (grand_done / grand_exp * 100) if grand_exp else 0
                table = (
                    "<table class='kob-dr-table'>"
                    "<thead><tr>"
                    "<th>Platform</th><th>Courier</th>"
                    "<th class='kob-dr-num'>Batches</th>"
                    "<th class='kob-dr-num'>Expected</th>"
                    "<th class='kob-dr-num'>Scanned</th>"
                    "<th class='kob-dr-num'>Pending</th>"
                    "<th>Progress</th>"
                    "<th>State</th>"
                    "</tr></thead>"
                    f"<tbody>{''.join(rows)}</tbody>"
                    "<tfoot><tr class='kob-dr-grand'>"
                    "<td colspan='3'><b>TOTAL</b></td>"
                    f"<td class='kob-dr-num'><b>{grand_exp}</b></td>"
                    f"<td class='kob-dr-num'><b>{grand_done}</b></td>"
                    f"<td class='kob-dr-num'><b>{grand_pending}</b></td>"
                    f"<td>"
                    f"<div class='kob-dr-bar'><div class='kob-dr-bar-fill' style='width:{int(grand_pct)}%'></div></div>"
                    f"<span class='kob-dr-bar-pct'><b>{grand_pct:.0f}%</b></span>"
                    f"</td>"
                    "<td></td>"
                    "</tr></tfoot>"
                    "</table>"
                )
            r.breakdown_html = table

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get("name", _("New")) == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "wms.dispatch.round"
                )
                v["name"] = seq or fields.Datetime.now().strftime(
                    "Round-%Y%m%d-%H%M"
                )
        return super().create(vals_list)

    @api.constrains("state", "company_id")
    def _check_single_open(self):
        for r in self.filtered(lambda x: x.state == "open"):
            others = self.search([
                ("state", "=", "open"),
                ("company_id", "=", r.company_id.id),
                ("id", "!=", r.id),
            ])
            if others:
                raise UserError(_(
                    "Another dispatch round is already open for %(co)s: %(name)s. "
                    "Close it before starting a new one."
                ) % {"co": r.company_id.name, "name": others[0].name})

    def action_close(self):
        for r in self:
            if r.state != "open":
                continue
            r.write({
                "state": "closed",
                "date_close": fields.Datetime.now(),
            })

    def action_reopen(self):
        for r in self:
            if r.state == "closed":
                # Refuse if there's already an open round for the same company
                open_round = self.search([
                    ("state", "=", "open"),
                    ("company_id", "=", r.company_id.id),
                ], limit=1)
                if open_round:
                    raise UserError(_(
                        "Cannot reopen — round %s is currently open."
                    ) % open_round.name)
                r.write({"state": "open", "date_close": False})

    @api.model
    def get_or_create_active(self, company=None):
        """Return the open round for the given company, creating one if
        no round is currently open. Used by action_ship override."""
        company = company or self.env.company
        existing = self.search([
            ("state", "=", "open"),
            ("company_id", "=", company.id),
        ], limit=1)
        if existing:
            return existing
        return self.sudo().create({
            "company_id": company.id,
            "label": fields.Datetime.now().strftime("Auto %Y-%m-%d %H:%M"),
        })

    @api.model
    def cron_auto_open_today(self):
        """Cron entry — make sure there is always an open round per company.
        Runs every 15 min as a safety net."""
        for company in self.env["res.company"].sudo().search([]):
            self.get_or_create_active(company)
        return True

    def action_open_batches(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Batches in %s") % self.name,
            "res_model": "wms.courier.batch",
            "view_mode": "list,form",
            "domain": [("dispatch_round_id", "=", self.id)],
            "context": {"default_dispatch_round_id": self.id},
        }
