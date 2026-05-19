# -*- coding: utf-8 -*-
"""Daily Pick Demand — aggregate report per (order_date, product).

Shows how much of each SKU is needed across all WMS orders for a
given order_date, how much already shipped, and the remaining
diff to pick. Useful for warehouse pre-pull at the start of each
shift.
"""
from odoo import models, fields, tools


class WmsDailyPickDemand(models.Model):
    _name = 'wms.daily.pick.demand'
    _description = 'Daily Pick Demand Report'
    _auto = False
    _order = 'order_date desc, expected_qty desc'

    order_date = fields.Date(string='Order Date', readonly=True)
    product_id = fields.Many2one(
        'product.product', string='Product', readonly=True)
    default_code = fields.Char(string='SKU', readonly=True)
    barcode = fields.Char(string='Barcode', readonly=True)
    expected_qty = fields.Float(
        string='Expected', readonly=True,
        help='Sum of expected_qty across every WMS line for this product '
             'on the order date.')
    pulled_qty = fields.Float(
        string='Pulled', readonly=True,
        help='Sum of picked_qty across every WMS line for this product '
             'on the order date — counts any qty that workers already '
             'scanned out, regardless of whether the order has shipped.')
    shipped_qty = fields.Float(
        string='Shipped', readonly=True,
        help='Sum of picked_qty where the WMS order has already reached '
             'shipped / packed status.')
    remaining_qty = fields.Float(
        string='Remaining', readonly=True,
        help='expected - pulled. The qty warehouse still needs to pick '
             'today for this SKU.')
    order_count = fields.Integer(
        string='Order Count', readonly=True,
        help='Distinct WMS orders that contain this SKU on the order date.')
    company_id = fields.Many2one(
        'res.company', string='Company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY DATE(COALESCE(wso.sale_order_date, wso.create_date)),
                                 wsol.product_id,
                                 wso.company_id
                    ) AS id,
                    DATE(COALESCE(wso.sale_order_date, wso.create_date)) AS order_date,
                    wsol.product_id AS product_id,
                    pp.default_code AS default_code,
                    pp.barcode AS barcode,
                    wso.company_id AS company_id,
                    SUM(wsol.expected_qty) AS expected_qty,
                    SUM(wsol.picked_qty) AS pulled_qty,
                    SUM(
                        CASE
                            WHEN wso.status IN ('shipped', 'packed')
                            THEN wsol.picked_qty
                            ELSE 0
                        END
                    ) AS shipped_qty,
                    GREATEST(
                        SUM(wsol.expected_qty) - SUM(wsol.picked_qty),
                        0
                    ) AS remaining_qty,
                    COUNT(DISTINCT wso.id) AS order_count
                FROM wms_sales_order_line wsol
                JOIN wms_sales_order wso ON wso.id = wsol.order_id
                LEFT JOIN product_product pp ON pp.id = wsol.product_id
                WHERE wsol.product_id IS NOT NULL
                  AND wso.status != 'cancelled'
                GROUP BY DATE(COALESCE(wso.sale_order_date, wso.create_date)),
                         wsol.product_id,
                         pp.default_code,
                         pp.barcode,
                         wso.company_id
            )
        """)
