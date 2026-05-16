# -*- coding: utf-8 -*-
"""Audit Trail HTTP endpoints — 3-way hash compare + Boat recovery.

Endpoints:
- /kob/api/audit/sales_order/<id>  → return audit status for OWL badge
- /kob/api/audit/recover/sales_order/<id>  → trigger Boat re-sync + reseal

Payload size goal: < 200 bytes. UI receives only digest summary, not
record details. Boat-side data never flows to browser — all hashing
done server-side in Odoo container, only result code returned.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class KobAuditController(http.Controller):

    @http.route(
        '/kob/api/audit/sales_order/<int:order_id>',
        type='json', auth='user', methods=['POST'], csrf=False,
    )
    def audit_sales_order(self, order_id, **_kw):
        """Return 3-way audit status for wms.sales.order(order_id).

        Result codes:
          VERIFIED    — sealed = current = boat
          DIVERGED    — sealed = current ≠ boat  (Boat moved on)
          TAMPERED    — sealed ≠ current         (KOB silently modified)
          UNSEALED    — no audit_hash yet (still in workflow)
          NOT_IN_BOAT — no x_boat_id link to Boat RDS
          BOAT_OFFLINE — psycopg2 connection failed
        """
        order = request.env['wms.sales.order'].sudo().browse(order_id)
        if not order.exists():
            return {'result': 'ERROR', 'message': 'not_found'}
        if not order.check_access_rights('read', raise_exception=False):
            return {'result': 'ERROR', 'message': 'forbidden'}
        try:
            return order.get_audit_status()
        except Exception as exc:  # noqa: BLE001
            _logger.exception('audit check failed for order %s', order_id)
            return {'result': 'ERROR', 'message': str(exc)[:200]}

    @http.route(
        '/kob/api/audit/recover/sales_order/<int:order_id>',
        type='json', auth='user', methods=['POST'], csrf=False,
    )
    def recover_sales_order(self, order_id, **_kw):
        """Trigger Boat re-sync for this record + reseal hash.

        Returns new audit status after recovery. Manager group gate
        enforced inside model method (action_recover_from_boat).
        """
        order = request.env['wms.sales.order'].browse(order_id)
        if not order.exists():
            return {'result': 'ERROR', 'message': 'not_found'}
        try:
            return order.action_recover_from_boat()
        except Exception as exc:  # noqa: BLE001
            _logger.exception('audit recover failed for order %s', order_id)
            return {'result': 'ERROR', 'message': str(exc)[:200]}
