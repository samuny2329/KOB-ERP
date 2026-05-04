from odoo import api, fields, models, _
from odoo.exceptions import UserError


# Inline stylesheet embedded in breakdown_html so the form-view html
# widget renders styled regardless of asset bundle state.
_INLINE_CSS = """
<style>
.kob-dr-card-bare {
  font-family: "Inter","Roboto","Segoe UI",-apple-system,"Helvetica Neue",Arial,"Noto Sans Thai",sans-serif;
  font-size: 13px; color: #4c4c4c; max-width: 1280px; margin: 8px 0;
}
.kob-dr-card-bare .kob-dr-section { margin: 14px 0 0; }
.kob-dr-card-bare .kob-dr-section__title {
  display: flex; align-items: baseline; gap: 10px; padding: 8px 4px;
  font-size: 11px; font-weight: 600; color: #6c757d;
  text-transform: uppercase; letter-spacing: 0.6px;
  border-bottom: 1px solid #f0f0f0;
}
.kob-dr-card-bare .kob-dr-section__name { color: #2c2c2c; }
.kob-dr-card-bare .kob-dr-section__icon { font-size: 14px; }
.kob-dr-card-bare .kob-dr-section__totals {
  margin-left: auto; font-size: 11px; font-weight: 400;
  color: #6c757d; text-transform: none; letter-spacing: 0;
}
.kob-dr-card-bare .kob-dr-section__totals b { color: #2c2c2c; font-weight: 600; }
.kob-dr-card-bare .kob-dr-section--warn .kob-dr-section__title {
  color: #b06000; border-bottom-color: #fde293;
}
.kob-dr-card-bare table.kob-dr-table {
  width: 100%; border-collapse: collapse; font-size: 13px; margin: 0;
}
.kob-dr-card-bare table.kob-dr-table thead th {
  text-align: left; font-weight: 500; color: #6c757d;
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px;
  padding: 10px 14px; background: #f6f6f6;
  border-bottom: 1px solid #e0e0e0; white-space: nowrap;
}
.kob-dr-card-bare table.kob-dr-table thead th.kob-dr-num { text-align: right; }
.kob-dr-card-bare table.kob-dr-table tbody td {
  padding: 9px 14px; border-bottom: 1px solid #f0f0f0; color: #4c4c4c;
  vertical-align: middle;
}
.kob-dr-card-bare table.kob-dr-table tbody td.kob-dr-num {
  text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap;
}
.kob-dr-card-bare table.kob-dr-table tbody td.kob-dr-platform {
  font-weight: 500; color: #2c2c2c; white-space: nowrap;
}
.kob-dr-card-bare table.kob-dr-table tbody tr:last-child td { border-bottom: 0; }
.kob-dr-card-bare table.kob-dr-table tbody tr:hover td { background: rgba(113,75,103,0.035); }
.kob-dr-card-bare table.kob-dr-table tfoot tr td {
  background: #f6f6f6; font-weight: 600; color: #2c2c2c;
  border-top: 1px solid #e0e0e0; border-bottom: 0; padding: 10px 14px;
}
.kob-dr-card-bare table.kob-dr-table tfoot tr td.kob-dr-num {
  text-align: right; font-variant-numeric: tabular-nums;
}
.kob-dr-card-bare .kob-dr-bar {
  display: inline-block; width: 90px; height: 6px;
  background: #f0f0f0; border-radius: 3px; overflow: hidden;
  vertical-align: middle; margin-right: 8px;
}
.kob-dr-card-bare .kob-dr-bar__fill {
  height: 100%; background: linear-gradient(90deg,#714B67 0%,#5d3a55 100%);
}
.kob-dr-card-bare .kob-dr-bar-pct { font-size: 11px; color: #6c757d; font-variant-numeric: tabular-nums; }
.kob-dr-card-bare .kob-dr-pill {
  display: inline-block; padding: 1px 8px; border-radius: 10px;
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;
  font-weight: 600; background: #f6f6f6; color: #6c757d;
  border: 1px solid #f0f0f0; white-space: nowrap;
}
.kob-dr-card-bare .kob-dr-pill--ok { background: #e6f4ea; color: #137333; border-color: #cae9d4; }
.kob-dr-card-bare .kob-dr-pill--warn { background: #fef7e0; color: #b06000; border-color: #fde293; }
.kob-dr-card-bare .kob-dr-pill--scanning { background: #e8f0fe; color: #1a73e8; border-color: #c2dafd; }
.kob-dr-card-bare .kob-dr-empty-block {
  text-align: center; color: #adb5bd; padding: 24px 16px;
  margin: 12px 0; border: 1px dashed #f0f0f0; border-radius: 4px; font-size: 12px;
}
.kob-dr-card-bare .kob-dr-empty-block--ok {
  background: #f0fdf4; color: #137333; border: 1px solid #cae9d4;
}
.kob-dr-card-bare .kob-dr-check {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; margin-left: 6px;
}
.kob-dr-card-bare .kob-dr-check--ok { color: #137333; }
.kob-dr-card-bare .kob-dr-check--bad { color: #c5221f; }
</style>
"""


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
        help="True when every non-cancelled batch is dispatched AND no "
             "upstream WIP orders remain (pick/pack/packed) in the same "
             "company. A round is genuinely 'done' only when nothing is "
             "still in flight.",
    )

    # Upstream WIP — orders that haven't reached the F3 scan-out step yet
    # but are in flight in the same company. Without this, a round can
    # show 100% complete while orders are still queued in pick/pack.
    wip_pick_count = fields.Integer(
        compute="_compute_wip", store=False,
        help="Orders currently in pending/picking — NOT yet picked.",
    )
    wip_pack_count = fields.Integer(
        compute="_compute_wip", store=False,
        help="Orders currently in picked/packing — picked but not packed.",
    )
    wip_packed_count = fields.Integer(
        compute="_compute_wip", store=False,
        help="Orders currently in packed — ready to ship at F3 but not yet "
             "scanned out, so no batch row exists yet.",
    )
    wip_total = fields.Integer(compute="_compute_wip", store=False)
    wip_breakdown_json = fields.Text(compute="_compute_wip", store=False)
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
            # is_complete is finalised by _compute_wip — see below.
            # Provisional value here.
            r.is_complete = bool(non_cx) and all(
                b.state == "dispatched" for b in non_cx
            )

    @api.depends("company_id", "state")
    def _compute_wip(self):
        """Count orders still upstream (pre-F3) for THIS round.

        Two cases:
        * Orders pre-tagged to this round via wms.sales.order.dispatch_round_id
          (Admin assigned them in Pick / Pack queues) → counted here.
        * Orders without a round tag → NOT counted here; they appear in
          the latest open round only via the global view, not this one.
        """
        SO = self.env.get("wms.sales.order")
        if SO is None:
            for r in self:
                r.wip_pick_count = 0
                r.wip_pack_count = 0
                r.wip_packed_count = 0
                r.wip_total = 0
                r.wip_breakdown_json = "[]"
            return
        SO = SO.sudo()

        import json
        for r in self:
            # Only count orders explicitly tagged to this round.
            domain = [
                ("dispatch_round_id", "=", r.id),
                ("status", "in",
                    ("pending", "picking", "picked", "packing", "packed")),
            ]
            wip = SO.search(domain)
            r.wip_pick_count = len(wip.filtered(
                lambda o: o.status in ("pending", "picking")
            ))
            r.wip_pack_count = len(wip.filtered(
                lambda o: o.status in ("picked", "packing")
            ))
            r.wip_packed_count = len(wip.filtered(
                lambda o: o.status == "packed"
            ))
            r.wip_total = len(wip)

            # Per-platform WIP rollup
            by_platform = {}
            for o in wip:
                p = getattr(o, "platform", None) or "manual"
                row = by_platform.setdefault(p, {
                    "platform": p, "pick": 0, "pack": 0, "packed": 0, "total": 0,
                })
                if o.status in ("pending", "picking"):
                    row["pick"] += 1
                elif o.status in ("picked", "packing"):
                    row["pack"] += 1
                elif o.status == "packed":
                    row["packed"] += 1
                row["total"] += 1
            r.wip_breakdown_json = json.dumps(
                sorted(by_platform.values(), key=lambda x: x["platform"]),
                ensure_ascii=False,
            )

            # Override is_complete: true only when batches dispatched AND
            # no orders left in the pipeline.
            if r.is_complete and r.wip_total > 0:
                r.is_complete = False

    @api.depends(
        "batch_ids", "batch_ids.scanned_count", "batch_ids.platform",
        "batch_ids.courier_id", "batch_ids.state",
        "batch_ids.expected_count", "batch_ids.scanned_done_count",
        "wip_breakdown_json",
    )
    def _compute_breakdown_html(self):
        """Render the round's full order pipeline as ONE coherent table.

        Each order in the round flows through:
            Pick (F1) → Pack (F2) → Packed → In Batch → Dispatched

        The main table groups orders by platform and counts how many
        sit at each stage. Row totals = sum of stages — math is honest
        and matches the imported cohort size (e.g. 2,947 imported
        orders show as 2,943 pick + 4 in-batch when only 4 reached F3).

        A secondary courier table drills the "In Batch" column down
        by courier so dispatch staff still see "3 Shopee scans for
        Shopee Express, 1 Tiktok for J&T".
        """
        platform_icons = {
            "shopee": "🛒", "lazada": "🟦", "tiktok": "🎵",
            "odoo": "🟣", "pos": "🏬", "manual": "✍️",
        }
        for r in self:
            non_cx = r.batch_ids.filtered(lambda b: b.state != "cancelled")
            # Group batches by (platform, courier) for the secondary
            # dispatch table.
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

            # ── Main pipeline table — orders × stage ───────────────────
            # An order belongs to this round if EITHER it is pre-tagged
            # via dispatch_round_id, OR it has a scan_item that landed
            # in one of this round's batches.
            SO = self.env.get("wms.sales.order")
            ScanItem = self.env.get("wms.scan.item")
            scan_so_ids = []
            if ScanItem is not None:
                scan_so_ids = ScanItem.sudo().search([
                    ("batch_id", "in", non_cx.ids),
                ]).mapped("sales_order_id").ids

            pipeline = {}   # platform -> {pick, pack, packed, in_batch, dispatched, total}
            if SO is not None:
                domain = [
                    "|",
                    ("dispatch_round_id", "=", r.id),
                    ("id", "in", scan_so_ids),
                ]
                cohort = SO.sudo().search(domain)
                # Map order_id → batch state (for shipped orders)
                so_batch_state = {}
                if ScanItem is not None and cohort:
                    items = ScanItem.sudo().search([
                        ("sales_order_id", "in", cohort.ids),
                        ("batch_id", "in", non_cx.ids),
                    ])
                    for it in items:
                        so_batch_state[it.sales_order_id.id] = it.batch_id.state

                for o in cohort:
                    p = getattr(o, "platform", None) or "manual"
                    bucket = pipeline.setdefault(p, {
                        "pick": 0, "pack": 0, "packed": 0,
                        "in_batch": 0, "dispatched": 0, "total": 0,
                    })
                    if o.status in ("pending", "picking"):
                        bucket["pick"] += 1
                    elif o.status in ("picked", "packing"):
                        bucket["pack"] += 1
                    elif o.status == "packed":
                        bucket["packed"] += 1
                    elif o.status == "shipped":
                        st = so_batch_state.get(o.id)
                        if st == "dispatched":
                            bucket["dispatched"] += 1
                        else:
                            bucket["in_batch"] += 1
                    bucket["total"] += 1

            pipeline_rows_html = []
            grand = {"pick": 0, "pack": 0, "packed": 0,
                     "in_batch": 0, "dispatched": 0, "total": 0}
            for platform, b in sorted(pipeline.items()):
                for k in grand:
                    grand[k] += b[k]
                pipeline_rows_html.append(
                    "<tr>"
                    f"<td class='kob-dr-platform'>"
                    f"{platform_icons.get(platform, '📦')} "
                    f"{platform.capitalize()}</td>"
                    f"<td class='kob-dr-num'>{b['pick']}</td>"
                    f"<td class='kob-dr-num'>{b['pack']}</td>"
                    f"<td class='kob-dr-num'>{b['packed']}</td>"
                    f"<td class='kob-dr-num'>{b['in_batch']}</td>"
                    f"<td class='kob-dr-num'>{b['dispatched']}</td>"
                    f"<td class='kob-dr-num'><b>{b['total']}</b></td>"
                    "</tr>"
                )

            if not pipeline_rows_html:
                pipeline_table = (
                    "<div class='kob-dr-empty-block'>"
                    "No orders in this round yet — assign orders from "
                    "Pick Queue (Actions → Assign to current dispatch round) "
                    "or wait for the first F3 scan to auto-attach."
                    "</div>"
                )
            else:
                # Consistency check: per-row total = sum of stages
                row_ok = all(
                    b["total"] == b["pick"] + b["pack"] + b["packed"]
                                + b["in_batch"] + b["dispatched"]
                    for b in pipeline.values()
                )
                grand_ok = grand["total"] == (
                    grand["pick"] + grand["pack"] + grand["packed"]
                    + grand["in_batch"] + grand["dispatched"]
                )
                check_html = (
                    "<span class='kob-dr-check kob-dr-check--ok'>"
                    "✓ totals consistent</span>"
                    if (row_ok and grand_ok) else
                    "<span class='kob-dr-check kob-dr-check--bad'>"
                    "⚠ totals mismatch</span>"
                )
                # Completion: % of cohort already shipped (in-batch + dispatched)
                done_n = grand["in_batch"] + grand["dispatched"]
                pct = (done_n / grand["total"] * 100) if grand["total"] else 0
                pipeline_table = (
                    "<div class='kob-dr-section'>"
                    "<div class='kob-dr-section__title'>"
                    "<span class='kob-dr-section__icon'>📋</span>"
                    "<span class='kob-dr-section__name'>"
                    "Order pipeline — this round</span>"
                    "<span class='kob-dr-section__totals'>"
                    f"<b>{grand['total']}</b> total · "
                    f"<b>{done_n}</b> shipped ({pct:.0f}%) · "
                    f"<b>{grand['pick'] + grand['pack'] + grand['packed']}</b> upstream"
                    f"{check_html}"
                    "</span>"
                    "</div>"
                    "<table class='kob-dr-table'>"
                    "<thead><tr>"
                    "<th>Platform</th>"
                    "<th class='kob-dr-num'>Pick (F1)</th>"
                    "<th class='kob-dr-num'>Pack (F2)</th>"
                    "<th class='kob-dr-num'>Packed</th>"
                    "<th class='kob-dr-num'>In Batch</th>"
                    "<th class='kob-dr-num'>Dispatched</th>"
                    "<th class='kob-dr-num'>Total</th>"
                    "</tr></thead>"
                    f"<tbody>{''.join(pipeline_rows_html)}</tbody>"
                    "<tfoot><tr>"
                    "<td><b>TOTAL</b></td>"
                    f"<td class='kob-dr-num'>{grand['pick']}</td>"
                    f"<td class='kob-dr-num'>{grand['pack']}</td>"
                    f"<td class='kob-dr-num'>{grand['packed']}</td>"
                    f"<td class='kob-dr-num'>{grand['in_batch']}</td>"
                    f"<td class='kob-dr-num'>{grand['dispatched']}</td>"
                    f"<td class='kob-dr-num'>{grand['total']}</td>"
                    "</tr></tfoot>"
                    "</table>"
                    "</div>"
                )

            # ── Secondary table: courier × platform (in-batch only) ─────
            rows = []
            grand_exp = grand_done = grand_pending = 0
            grand_batches = 0
            for (platform, courier), v in sorted(groups.items()):
                grand_exp += v["expected"]
                grand_done += v["scanned"]
                grand_pending += v["pending"]
                grand_batches += v["batches"]
                pct = (v["scanned"] / v["expected"] * 100) if v["expected"] else 0
                done = all(s == "dispatched" for s in v["states"])
                if done:
                    state_cell = "<span class='kob-dr-pill kob-dr-pill--ok'>✓ done</span>"
                elif v["pending"] == 0:
                    state_cell = "<span class='kob-dr-pill kob-dr-pill--scanning'>ready to dispatch</span>"
                else:
                    state_cell = (
                        f"<span class='kob-dr-pill kob-dr-pill--warn'>"
                        f"⏳ {v['pending']} pending</span>"
                    )
                rows.append(
                    "<tr>"
                    f"<td class='kob-dr-platform'>"
                    f"{platform_icons.get(platform, '📦')} {platform.capitalize()}"
                    "</td>"
                    f"<td>{courier}</td>"
                    f"<td class='kob-dr-num'>{v['batches']}</td>"
                    f"<td class='kob-dr-num'>{v['expected']}</td>"
                    f"<td class='kob-dr-num'>{v['scanned']}</td>"
                    f"<td class='kob-dr-num'>{v['pending']}</td>"
                    "<td>"
                    f"<div class='kob-dr-bar'><div class='kob-dr-bar__fill' style='width:{int(pct)}%'></div></div>"
                    f"<span class='kob-dr-bar-pct'>{pct:.0f}%</span>"
                    "</td>"
                    f"<td>{state_cell}</td>"
                    "</tr>"
                )

            if not rows:
                table = ""  # main pipeline table already covers the empty case
            else:
                grand_pct = (grand_done / grand_exp * 100) if grand_exp else 0
                # Consistency check: pending = expected - scanned
                check_ok = grand_pending == max(0, grand_exp - grand_done)
                check_html = (
                    "<span class='kob-dr-check kob-dr-check--ok'>"
                    "✓ matches In Batch column above</span>"
                    if check_ok else
                    "<span class='kob-dr-check kob-dr-check--bad'>"
                    f"⚠ pending ({grand_pending}) ≠ expected − scanned "
                    f"({grand_exp - grand_done})</span>"
                )
                table = (
                    "<div class='kob-dr-section'>"
                    "<div class='kob-dr-section__title'>"
                    "<span class='kob-dr-section__icon'>📦</span>"
                    "<span class='kob-dr-section__name'>"
                    "Dispatch detail — In Batch by courier (F3/F4)"
                    "</span>"
                    "<span class='kob-dr-section__totals'>"
                    f"<b>{grand_batches}</b> batches · "
                    f"<b>{grand_exp}</b> in-batch · "
                    f"<b>{grand_done}</b> scanned · "
                    f"<b>{grand_pending}</b> pending"
                    f"{check_html}"
                    "</span>"
                    "</div>"
                    "<table class='kob-dr-table'>"
                    "<thead><tr>"
                    "<th>Platform</th>"
                    "<th>Courier</th>"
                    "<th class='kob-dr-num'>Batches</th>"
                    "<th class='kob-dr-num'>In Batch</th>"
                    "<th class='kob-dr-num'>Scanned</th>"
                    "<th class='kob-dr-num'>Pending</th>"
                    "<th>Progress</th>"
                    "<th>State</th>"
                    "</tr></thead>"
                    f"<tbody>{''.join(rows)}</tbody>"
                    "<tfoot><tr>"
                    "<td><b>TOTAL</b></td>"
                    "<td></td>"
                    f"<td class='kob-dr-num'>{grand_batches}</td>"
                    f"<td class='kob-dr-num'>{grand_exp}</td>"
                    f"<td class='kob-dr-num'>{grand_done}</td>"
                    f"<td class='kob-dr-num'>{grand_pending}</td>"
                    "<td>"
                    f"<div class='kob-dr-bar'><div class='kob-dr-bar__fill' "
                    f"style='width:{int(grand_pct)}%'></div></div>"
                    f"<span class='kob-dr-bar-pct'>{grand_pct:.0f}%</span>"
                    "</td>"
                    "<td></td>"
                    "</tr></tfoot>"
                    "</table>"
                    "</div>"
                )

            # The Upstream WIP table is no longer rendered separately —
            # the main pipeline table above already shows Pick/Pack/Packed
            # columns. Keeping the data exposed via the wip_total field
            # for the stat button + Daily Report aggregation.

            # Wrap output in a bare card so the embedded form view shows
            # a tidy white surface around both tables. Inline <style>
            # guards against asset bundle cache misses on freshly-
            # restarted Odoo containers.
            r.breakdown_html = (
                _INLINE_CSS
                + "<div class='kob-dr-card-bare'>"
                + pipeline_table + table
                + "</div>"
            )

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
