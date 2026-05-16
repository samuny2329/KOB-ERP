from odoo import _, fields, models


class ThitiItemSupplier(models.Model):
    _name = "thiti.item.supplier"
    _description = "Thiti Item-Supplier (sourcing rule)"
    _inherit = ["mail.thread"]
    _order = "item_id, priority, supplier_id"

    item_id = fields.Many2one(
        "thiti.item", required=True, index=True, ondelete="cascade", tracking=True,
    )
    supplier_id = fields.Many2one(
        "thiti.supplier", required=True, index=True, ondelete="restrict", tracking=True,
    )
    location_id = fields.Many2one(
        "thiti.location", string="Destination Location", index=True,
    )
    odoo_supplierinfo_id = fields.Many2one(
        "product.supplierinfo", string="Linked Odoo Supplier Info", index=True,
    )
    priority = fields.Integer(default=1, tracking=True)
    lead_time_days = fields.Float(default=0.0, tracking=True)
    cost = fields.Float(tracking=True, digits="Product Price")
    sizeminimum = fields.Float(string="Min Order Qty", default=1.0)
    sizemultiple = fields.Float(string="Order Multiple", default=1.0)
    sizemaximum = fields.Float(string="Max Order Qty")
    effective_start = fields.Datetime()
    effective_end = fields.Datetime()
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)

    _sql_constraints = [
        ("item_supplier_unique",
         "UNIQUE(item_id, supplier_id, location_id, priority)",
         _("Duplicate item-supplier rule for same priority.")),
    ]
