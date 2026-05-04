"""Override wms.sales.order.action_ship so that scan items are routed into
courier batches keyed by (round, courier, platform) instead of just
(courier)."""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


PARAM_AUTO_BATCH = "kob_wms_auto_batch.auto_batch_per_platform"


class WmsSalesOrder(models.Model):
    _inherit = "wms.sales.order"

    def action_ship(self):
        # Auto-resolve courier BEFORE parent runs — otherwise parent skips
        # scan_item creation when courier_id is empty (line 861 in kob_wms).
        for order in self:
            if not order.courier_id:
                resolved = order._kob_resolve_default_courier()
                if resolved:
                    order.with_context(skip_track=True).courier_id = resolved.id

        # Capture pre-ship state per order so we can detect new scan items.
        ScanItem = self.env["wms.scan.item"]
        before_ids = {
            o.id: set(ScanItem.search([("sales_order_id", "=", o.id)]).ids)
            for o in self
        }

        result = super().action_ship()

        # If parent rejected the ship, bail.
        if isinstance(result, dict) and result.get("ok") is False:
            return result

        param = self.env["ir.config_parameter"].sudo().get_param(
            PARAM_AUTO_BATCH, default="True",
        )
        platform_grouping = str(param).lower() in ("1", "true", "yes")

        Round = self.env["wms.dispatch.round"].sudo()
        Batch = self.env["wms.courier.batch"].sudo()

        for order in self:
            new_items = ScanItem.search([
                ("sales_order_id", "=", order.id),
                ("id", "not in", list(before_ids.get(order.id, set()))),
            ])
            if not new_items:
                continue

            active_round = Round.get_or_create_active(order.company_id)

            for item in new_items:
                if not item.courier_id:
                    continue
                # Always set platform on the scan item itself
                item.write({"platform": order.platform or "manual"})
                target_batch = self._kob_pick_batch(
                    Batch, active_round, order, platform_grouping,
                )
                # Only re-link if parent assigned to a different batch that
                # doesn't match our routing key
                if not item.batch_id or item.batch_id != target_batch:
                    item.write({"batch_id": target_batch.id})

        return result

    def _kob_pick_batch(self, Batch, active_round, order, platform_grouping):
        """Find an open scanning batch matching the routing key, else create
        one. Routing key:
            (round, courier, [platform if grouping enabled])
        """
        domain = [
            ("state", "=", "scanning"),
            ("courier_id", "=", order.courier_id.id),
            ("dispatch_round_id", "=", active_round.id),
        ]
        platform = order.platform or "manual"
        if platform_grouping:
            domain.append(("platform", "=", platform))

        batch = Batch.search(domain, limit=1)
        if batch:
            return batch

        # Migrate a legacy batch that has no round set yet, if it matches
        # the (courier, platform-or-none) key — keeps current scans together
        # the first time the new module is installed.
        legacy_domain = [
            ("state", "=", "scanning"),
            ("courier_id", "=", order.courier_id.id),
            ("dispatch_round_id", "=", False),
        ]
        if platform_grouping:
            legacy_domain.append(
                "|"
            )
            legacy_domain.append(("platform", "=", platform))
            legacy_domain.append(("platform", "=", False))
        legacy = Batch.search(legacy_domain, limit=1)
        if legacy:
            legacy.write({
                "dispatch_round_id": active_round.id,
                "platform": platform if platform_grouping else legacy.platform,
            })
            return legacy

        return Batch.create({
            "state": "scanning",
            "courier_id": order.courier_id.id,
            "dispatch_round_id": active_round.id,
            "platform": platform if platform_grouping else False,
        })
