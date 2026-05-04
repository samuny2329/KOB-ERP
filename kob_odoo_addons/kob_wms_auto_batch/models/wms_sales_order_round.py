"""Pre-tag wms.sales.order with a dispatch round.

Admin selects orders (in Pick Queue, Pack Queue, etc.) and runs the
"Assign to current round" Action — those SOs get `dispatch_round_id`
set so the round form can show "this round has 80 orders allocated;
3 picked, 2 packed, 75 still pending pick" instead of counting the
whole company's WIP.

When action_ship eventually runs for a tagged SO, the scan_item joins
the SO's round (not the round currently active) — so a round opened
in the morning still receives its orders even if shipping happens
late afternoon.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WmsSalesOrder(models.Model):
    _inherit = "wms.sales.order"

    dispatch_round_id = fields.Many2one(
        "wms.dispatch.round",
        string="Dispatch Round",
        index=True,
        ondelete="set null",
        copy=False,
        tracking=True,
        help="Round this order belongs to. Set by the 'Assign to "
             "current round' Action on the Pick / Pack queues. When "
             "empty, the order falls into whichever round is open at "
             "F3 ship time.",
    )
    dispatch_round_state = fields.Selection(
        related="dispatch_round_id.state",
        store=True,
        readonly=True,
    )

    def action_assign_to_active_round(self):
        """Server-action target. For each selected SO, tag with the
        currently open round of the SO's company (auto-create if none).
        Skips already-tagged orders so re-running is safe."""
        Round = self.env["wms.dispatch.round"].sudo()
        per_company = {}
        moved = 0
        skipped = 0
        for so in self:
            company = so.company_id or self.env.company
            if so.dispatch_round_id and so.dispatch_round_id.state == "open":
                skipped += 1
                continue
            r = per_company.get(company.id)
            if r is None:
                r = Round.get_or_create_active(company)
                per_company[company.id] = r
            so.dispatch_round_id = r.id
            moved += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Assign to round"),
                "message": _(
                    "%(m)s order(s) tagged to the active round; %(s)s "
                    "already tagged."
                ) % {"m": moved, "s": skipped},
                "type": "success",
                "sticky": False,
            },
        }

    def action_clear_dispatch_round(self):
        """Untag — useful if Admin assigned the wrong orders."""
        self.write({"dispatch_round_id": False})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Cleared round"),
                "message": _("%s order(s) unlinked from their round.") % len(self),
                "type": "info",
                "sticky": False,
            },
        }
