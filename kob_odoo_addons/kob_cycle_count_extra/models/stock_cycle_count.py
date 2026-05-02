# -*- coding: utf-8 -*-
from odoo import api, models


class StockCycleCount(models.Model):
    _inherit = "stock.cycle.count"

    @api.onchange("cycle_count_rule_id")
    def _onchange_rule_autofill_location(self):
        """When a rule is selected, auto-set Location to the deepest common
        ancestor of all locations the rule applies to.

        - PF-A rule → 50 bins under K-On/Stock/PICKFACE → Location = PICKFACE
        - Single-location rule → Location = that exact location
        - No locations linked → leave blank
        """
        rule = self.cycle_count_rule_id
        if not rule:
            return
        # OCA M2M: stock.cycle.count.rule.location_ids → stock.location
        # (or via warehouse_ids depending on apply_in)
        locs = rule.location_ids if "location_ids" in rule._fields else rule.mapped(
            "warehouse_ids.lot_stock_id",
        )
        if not locs:
            return
        if len(locs) == 1:
            self.location_id = locs.id
            return
        # Find deepest common ancestor by parent_path overlap
        # parent_path looks like "/1/5/511/1234/" — split & find longest shared prefix
        paths = [
            (loc.parent_path or "").strip("/").split("/")
            for loc in locs
        ]
        common = []
        for parts in zip(*paths):
            if len(set(parts)) == 1:
                common.append(parts[0])
            else:
                break
        if common:
            ancestor_id = int(common[-1])
            self.location_id = ancestor_id
        else:
            # Fallback: use first location
            self.location_id = locs[0].id
