# Override stock.location.usage label: 'view' → 'View' (default in Odoo 19 is 'Virtual')
from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    usage = fields.Selection(
        selection=[
            ("supplier", "Vendor"),
            ("view", "View"),
            ("internal", "Internal"),
            ("customer", "Customer"),
            ("inventory", "Inventory Loss"),
            ("production", "Production"),
            ("transit", "Transit"),
        ],
    )
