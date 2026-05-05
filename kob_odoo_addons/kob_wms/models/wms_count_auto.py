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

    def _generate_location_tasks(self, session):
        """Fallback when ABC produces no tasks.

        Creates one task per **(location, product)** pair from on-hand
        stock — same shape as ABC tasks (specific SKU + expected_qty
        pre-filled from stock_quant). Without this, workers got blank
        ``[LOC] <location>`` rows with 0 expected qty and nothing to
        count, defeating the purpose of cycle count.
        """
        warehouse = session.warehouse_id
        domain = [('usage', '=', 'internal')]
        if warehouse:
            # Restrict to locations under this warehouse's view location
            parent = warehouse.lot_stock_id.location_id
            if parent:
                domain += [('id', 'child_of', parent.id)]

        # Pull all on-hand quants in matching locations in one query
        locations = self.env['stock.location'].search(domain)
        if not locations:
            return
        quants = self.env['stock.quant'].search([
            ('location_id', 'in', locations.ids),
            ('quantity', '>', 0),
            ('product_id', '!=', False),
        ])

        Task = self.env['wms.count.task']
        created = 0
        # Aggregate by (location, product) — sum lots so one task covers
        # the whole pickface bin per SKU.
        bucket = {}
        for q in quants:
            key = (q.location_id.id, q.product_id.id)
            bucket.setdefault(key, 0.0)
            bucket[key] += q.quantity

        for (loc_id, product_id), expected in bucket.items():
            Task.create({
                'session_id': session.id,
                'location_id': loc_id,
                'product_id': product_id,
                'expected_qty': expected,
                # name is auto-assigned via ir.sequence (CT/YYYY/####)
            })
            created += 1

        _logger.info(
            'Auto cycle count fallback: created %d (loc,product) task(s) '
            'for %s.', created, session.name,
        )
