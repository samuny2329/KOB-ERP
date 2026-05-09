"""Stock Valuation at Date wizard.

Mimics the 'Valuation at Date' button on enterprise/Odoo 18 Stock Valuation
report. Worker picks a historical datetime; the wizard reopens the standard
Stock Valuation list view filtered to ``date <= snapshot_date AND state =
done`` so all subsequent moves are excluded — effectively a snapshot.
"""
from odoo import api, fields, models


class WmsStockValuationDateWizard(models.TransientModel):
    _name = "wms.stock.valuation.date.wizard"
    _description = "Stock Valuation at Date Wizard"

    snapshot_date = fields.Datetime(
        string="As of Date",
        required=True,
        default=lambda self: fields.Datetime.now(),
        help="Show the stock valuation as it stood at this date and time. "
             "All stock.move records done after this datetime are excluded.",
    )
    note = fields.Text(readonly=True, default=(
        "Pick a historical datetime to view the Stock Valuation snapshot. "
        "Click 'Open Snapshot' to load the list/pivot/graph view filtered "
        "to moves completed on or before that point."
    ))

    def action_open_snapshot(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Stock Valuation as of %s" % fields.Datetime.to_string(
                self.snapshot_date),
            "res_model": "stock.move",
            "view_mode": "list,form,pivot,graph",
            "domain": [
                ("date", "<=", self.snapshot_date),
                ("state", "=", "done"),
                "|", ("is_in", "=", True), ("is_out", "=", True),
            ],
            "context": {
                "search_default_done": 1,
                "kob_valuation_snapshot": str(self.snapshot_date),
            },
        }
