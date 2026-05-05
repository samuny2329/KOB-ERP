from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class WmsCountSessionAuto(models.Model):
    """Cron-driven auto cycle count generation.

    Two call paths:
      • Cron  — self is empty recordset → creates new session, generates tasks,
                starts + broadcasts.  Skipped if a session already exists today.
      • Button — self is the current draft session → generate tasks into it,
                 start + broadcast.  Does NOT create another session.

    If ABC classification produces 0 tasks (no pickface/sales data), the method
    falls back to generating one task per internal stock location that has stock.
    """
    _inherit = 'wms.count.session'

    def action_auto_cycle_count(self):
        """Entry point for the daily cron AND the 'Run Now' button."""

        # ── Determine session ────────────────────────────────────────
        if self:
            # Button call: use the current (draft) session
            session = self[0]
            if session.state != 'draft':
                raise UserError(_('Session must be in Draft state to run auto count.'))
        else:
            # Cron call: skip if a cycle session already exists today
            today_start = fields.Datetime.to_datetime(fields.Date.today())
            existing = self.search([
                ('session_type', '=', 'cycle'),
                ('state', 'in', ('draft', 'in_progress')),
                ('date_start', '>=', today_start),
            ], limit=1)
            if existing:
                _logger.info(
                    'Auto cycle count: session %s already exists today — skipped.',
                    existing.name,
                )
                return existing

            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', self.env.company.id)], limit=1)
            if not warehouse:
                _logger.warning('Auto cycle count: no warehouse configured — aborted.')
                return

            session = self.create({
                'session_type': 'cycle',
                'warehouse_id': warehouse.id,
                'responsible_id': self.env.ref('base.user_admin').id,
            })

        # ── Generate ABC tasks ───────────────────────────────────────
        session.action_generate_abc_tasks()

        # ── Fallback: location-based tasks if ABC yields nothing ─────
        if not session.task_ids:
            _logger.info(
                'Auto cycle count: ABC yielded 0 tasks for %s — '
                'falling back to location scan.', session.name,
            )
            self._generate_location_tasks(session)

        if not session.task_ids:
            raise UserError(_(
                'ไม่สามารถสร้าง Count Task ได้\n\n'
                'ระบบ ABC ต้องการข้อมูล Sales Order + Pickface\n'
                'Fallback ต้องการ stock.location ที่มีสินค้าอยู่\n\n'
                'กรุณาตรวจสอบ Inventory → Zones / Racks / Pickfaces'
            ))

        # ── Start + broadcast to all workers ────────────────────────
        session.action_start()
        session.task_ids.write({'state': 'assigned'})

        _logger.info(
            'Auto cycle count: session %s started — %d task(s) broadcast.',
            session.name, len(session.task_ids),
        )
        return session

    # ── Fallback ABC sample sizes (when sales-data ABC yields nothing) ──
    # Stock-based ABC ranks each (loc, product) by ON-HAND qty.  Sample
    # caps are bigger than the sales-based version because this branch
    # only fires when there are no recent orders to drive the smaller
    # daily sample — so we still want SOME coverage but never thousands.
    _STOCK_ABC_SAMPLE = {
        'A': {'pct': 0.20, 'max': 30},   # top 20% of products by qty
        'B': {'pct': 0.10, 'max': 20},   # next 30%
        'C': {'pct': 0.05, 'max': 10},   # bottom 50%
    }

    def _generate_location_tasks(self, session):
        """Fallback when sales-based ABC produces no tasks.

        Builds (location, product) pairs from on-hand stock, ranks them
        A/B/C by total on-hand qty per product (top 20% / next 30% /
        rest = A/B/C), then takes a **weighted random sample** per rank
        so a typical session ends up with at most ~60 tasks instead of
        the entire warehouse (which is what produced the 11,994-task
        sessions seen in the wild).
        """
        import math
        import random

        warehouse = session.warehouse_id
        domain = [('usage', '=', 'internal')]
        if warehouse:
            parent = warehouse.lot_stock_id.location_id
            if parent:
                domain += [('id', 'child_of', parent.id)]

        locations = self.env['stock.location'].search(domain)
        if not locations:
            return
        quants = self.env['stock.quant'].search([
            ('location_id', 'in', locations.ids),
            ('quantity', '>', 0),
            ('product_id', '!=', False),
        ])
        if not quants:
            return

        # Aggregate qty per (location, product) — this is the candidate
        # pool we'll sample from.
        bucket = {}
        for q in quants:
            key = (q.location_id.id, q.product_id.id)
            bucket[key] = bucket.get(key, 0.0) + q.quantity

        # Per-product total qty (across all locations) → ABC rank.
        per_product = {}
        for (_loc, pid), qty in bucket.items():
            per_product[pid] = per_product.get(pid, 0.0) + qty

        ranked = sorted(per_product.items(), key=lambda x: x[1], reverse=True)
        n_products = len(ranked)
        a_cut = max(1, int(n_products * 0.20))
        b_cut = max(a_cut + 1, int(n_products * 0.50))
        rank_map = {}
        for i, (pid, _q) in enumerate(ranked):
            rank_map[pid] = 'A' if i < a_cut else ('B' if i < b_cut else 'C')

        # Group bucket entries by ABC rank — each entry = (loc, pid, qty).
        by_rank = {'A': [], 'B': [], 'C': []}
        for (loc_id, pid), qty in bucket.items():
            r = rank_map[pid]
            by_rank[r].append((loc_id, pid, float(qty)))

        # Cycle count: skip C (count C only in full counts).
        if session.session_type == 'cycle':
            by_rank['C'] = []

        # Weighted random sample per rank (weight = qty).
        chosen = []
        for r, items in by_rank.items():
            if not items:
                continue
            cfg = self._STOCK_ABC_SAMPLE[r]
            n = min(cfg['max'], max(1, math.ceil(len(items) * cfg['pct'])))
            n = min(n, len(items))
            # Weighted sample without replacement
            pool = list(items)
            for _ in range(n):
                if not pool:
                    break
                total_w = sum(w for _, _, w in pool)
                pick = random.uniform(0, total_w)
                acc = 0.0
                for idx, (loc, pid, w) in enumerate(pool):
                    acc += w
                    if acc >= pick:
                        chosen.append((loc, pid, w, r))
                        pool.pop(idx)
                        break

        Task = self.env['wms.count.task']
        a_n = b_n = c_n = 0
        for loc_id, pid, expected, rank in chosen:
            product = self.env['product.product'].browse(pid)
            Task.create({
                'session_id': session.id,
                'location_id': loc_id,
                'product_id': pid,
                'expected_qty': expected,
                'abc_label': _('[%s] Count %s') % (
                    rank, product.default_code or str(pid)),
            })
            if rank == 'A': a_n += 1
            elif rank == 'B': b_n += 1
            else: c_n += 1

        session.message_post(body=_(
            'Stock-based ABC fallback: %d tasks — A=%d, B=%d, C=%d '
            '(sampled from %d candidate (loc,product) pairs across '
            '%d distinct products)'
        ) % (len(chosen), a_n, b_n, c_n, len(bucket), n_products))
        _logger.info(
            'Auto cycle count fallback: created %d task(s) for %s '
            '(A=%d B=%d C=%d, from %d candidates).',
            len(chosen), session.name, a_n, b_n, c_n, len(bucket),
        )
