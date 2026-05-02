# -*- coding: utf-8 -*-
from odoo import api, models


class StockCycleCount(models.Model):
    _inherit = "stock.cycle.count"

    @api.onchange("cycle_count_rule_id")
    def _onchange_rule_autofill_location(self):
        """When a rule is selected, auto-set Location to the FIRST specific
        bin in the rule's location_ids list.

        OCA constraint: stock.inventory linked to cycle_count must have
        exclude_sublocation=True (i.e. count one specific bin only). So we
        cannot set Location to a parent like PICKFACE — we must pick one
        leaf bin. The cycle count generation cron will rotate through the
        rule's bins automatically across periods.

        - PF-A rule → 50 bins → Location = PF-A-1-01 (first bin)
        - Single-location rule → that exact bin
        """
        rule = self.cycle_count_rule_id
        if not rule:
            return
        locs = rule.location_ids if "location_ids" in rule._fields else rule.mapped(
            "warehouse_ids.lot_stock_id",
        )
        if not locs:
            return
        # Always pick first bin (OCA requires leaf-bin counting)
        self.location_id = locs[0].id
