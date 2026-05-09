"""Pickface-first reservation override.

Forces outbound delivery moves to source from the product's assigned
``wms.pickface`` location instead of the parent stock zone (e.g.
K-On/Stock or B-On/Stock). Bulk zones become reserve-only — orders
are picked from pickface; pickfaces are replenished from bulk via
``wms.pickface.action_create_restock_transfer()``.

Behaviour:
    1. For each outbound move (picking_type.code == 'outgoing') with a
       product that has an assigned active pickface, redirect
       ``move.location_id`` to the pickface location BEFORE Odoo's
       native reservation runs.
    2. If pickface stock < move qty, leave the source as-is — Odoo's
       reservation falls back to whatever quants are available in the
       parent zone (legacy behaviour). The pickface's
       ``needs_restock`` flag will pick this up and the cron creates a
       Bulk → Pickface internal transfer.
    3. Internal moves (Bulk → Pickface restock transfers) are NOT
       affected — they keep their original source.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _kob_redirect_to_pickface(self):
        """Rewrite location_id to product's pickface for outbound moves.

        Called from ``_action_assign`` before reservation. Silent: any
        failure (no pickface, missing warehouse, etc.) leaves the move
        unchanged so picking is never broken by this override.
        """
        Pickface = self.env['wms.pickface']
        for move in self:
            try:
                if move.state in ('done', 'cancel'):
                    continue
                pt = move.picking_type_id
                if not pt or pt.code != 'outgoing':
                    continue
                if not move.product_id:
                    continue
                # Already sourced from a PICKFACE child? Skip.
                cur_loc = move.location_id
                if cur_loc and 'PICKFACE' in (cur_loc.complete_name or ''):
                    continue
                # Find an active pickface for this product whose location
                # sits under the current source zone.
                pf = Pickface.search([
                    ('product_id', '=', move.product_id.id),
                    ('active', '=', True),
                    ('location_id', 'child_of', cur_loc.id),
                ], limit=1)
                if not pf or not pf.location_id:
                    continue
                # Only redirect if the pickface has enough physical stock
                # to cover this move; otherwise let the bulk zone fall
                # back so the order is not blocked while restock is queued.
                if pf.current_qty < move.product_uom_qty:
                    if pf.needs_restock:
                        # Best-effort: queue a restock if not already queued.
                        # Failures are silenced — the order continues from bulk.
                        try:
                            pf.action_create_restock_transfer()
                        except Exception as exc:  # noqa: BLE001
                            _logger.info(
                                "Auto-restock for %s skipped: %s",
                                pf.code, exc)
                    continue
                move.write({'location_id': pf.location_id.id})
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "Pickface redirect skipped for move %s: %s",
                    move.id, exc)

    def _action_assign(self, force_qty=False):
        # Redirect first, then call the standard reservation path.
        self._kob_redirect_to_pickface()
        return super()._action_assign(force_qty=force_qty)
