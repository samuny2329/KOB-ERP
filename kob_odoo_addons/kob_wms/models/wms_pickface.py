from odoo import models, fields, api, _


class WmsPickface(models.Model):
    _name = 'wms.pickface'
    _description = 'WMS Pickface (Pick Bin)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code'

    name = fields.Char(string='Pickface Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    zone_id = fields.Many2one('wms.zone', string='Zone', required=True)
    product_id = fields.Many2one('product.product', string='Assigned Product',
                                 tracking=True)
    location_id = fields.Many2one('stock.location', string='Stock Location')
    min_qty = fields.Float(string='Min Level', default=0.0,
                           help='Legacy threshold. Demand-driven restock '
                                'ignores this if pending_demand > 0.')
    max_qty = fields.Float(string='Max Level', default=0.0,
                           help='Legacy ceiling. Demand-driven restock '
                                'sizes transfers from pending_demand only.')
    current_qty = fields.Float(string='Current Qty',
                               compute='_compute_current_qty', store=True)
    pending_demand = fields.Float(
        string='Pending Demand',
        compute='_compute_demand', store=True,
        help='Sum of unfulfilled outbound move qty for this product whose '
             'source location is the pickface (ready/confirmed/waiting). '
             'This is the qty workers still need to pick.',
    )
    in_transit_qty = fields.Float(
        string='Inbound Restock',
        compute='_compute_demand', store=True,
        help='Qty already on the way to this pickface from open Bulk → '
             'Pickface internal transfers (not yet validated). Subtracted '
             'from restock_qty to avoid duplicate transfers.',
    )
    restock_qty = fields.Float(string='Restock Qty',
                               compute='_compute_restock_qty', store=True)
    needs_restock = fields.Boolean(string='Needs Restock',
                                   compute='_compute_needs_restock', store=True)
    company_id = fields.Many2one('res.company', related='zone_id.company_id',
                                 store=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code, zone_id)',
         'Pickface code must be unique per zone!'),
    ]

    @api.depends('product_id', 'location_id')
    def _compute_current_qty(self):
        # Batch-fetch all quants in one query to avoid N+1
        pf_with_data = self.filtered(lambda p: p.product_id and p.location_id)
        if pf_with_data:
            quants = self.env['stock.quant'].sudo().search([
                ('product_id', 'in', pf_with_data.mapped('product_id').ids),
                ('location_id', 'in', pf_with_data.mapped('location_id').ids),
            ])
            # Index by (product_id, location_id) for O(1) lookup
            qty_map = {}
            for q in quants:
                key = (q.product_id.id, q.location_id.id)
                qty_map[key] = qty_map.get(key, 0) + q.quantity
        else:
            qty_map = {}

        for pf in self:
            if pf.product_id and pf.location_id:
                pf.current_qty = qty_map.get((pf.product_id.id, pf.location_id.id), 0)
            else:
                pf.current_qty = 0

    @api.depends('product_id', 'location_id')
    def _compute_demand(self):
        """Compute pending outbound demand + inbound restock-in-flight per pickface.

        pending_demand = sum of stock.move.product_uom_qty (state in
            confirmed/waiting/partially_available/assigned) for outbound
            picking_type whose source location is THIS pickface.
        in_transit_qty = sum of stock.move.product_uom_qty (state in
            confirmed/waiting/partially_available/assigned) for INTERNAL
            picking_type whose destination location is THIS pickface.
        """
        Move = self.env['stock.move'].sudo()
        active_states = ('waiting', 'confirmed', 'partially_available',
                         'assigned')
        for pf in self:
            if not pf.product_id or not pf.location_id:
                pf.pending_demand = 0.0
                pf.in_transit_qty = 0.0
                continue
            outbound = Move.search([
                ('product_id', '=', pf.product_id.id),
                ('location_id', '=', pf.location_id.id),
                ('state', 'in', active_states),
                ('picking_type_id.code', '=', 'outgoing'),
            ])
            inbound = Move.search([
                ('product_id', '=', pf.product_id.id),
                ('location_dest_id', '=', pf.location_id.id),
                ('state', 'in', active_states),
                ('picking_type_id.code', '=', 'internal'),
            ])
            pf.pending_demand = sum(outbound.mapped('product_uom_qty'))
            pf.in_transit_qty = sum(inbound.mapped('product_uom_qty'))

    @api.depends('current_qty', 'pending_demand', 'in_transit_qty', 'max_qty')
    def _compute_restock_qty(self):
        """Demand-driven restock sizing.

        restock_qty = max(0, pending_demand - current_qty - in_transit_qty)
        Falls back to legacy (max_qty - current_qty) ONLY when no demand
        and the pickface has a configured max_qty.
        """
        for pf in self:
            net_need = (pf.pending_demand or 0.0) \
                - (pf.current_qty or 0.0) \
                - (pf.in_transit_qty or 0.0)
            if net_need > 0:
                pf.restock_qty = net_need
            elif pf.max_qty and pf.current_qty < pf.max_qty:
                pf.restock_qty = pf.max_qty - pf.current_qty
            else:
                pf.restock_qty = 0.0

    @api.depends('current_qty', 'pending_demand', 'in_transit_qty', 'min_qty')
    def _compute_needs_restock(self):
        """Trigger when:
            (a) demand > available + in-flight stock, OR
            (b) legacy: current_qty <= min_qty (when min_qty set).
        """
        for pf in self:
            avail = (pf.current_qty or 0.0) + (pf.in_transit_qty or 0.0)
            demand_gap = (pf.pending_demand or 0.0) > avail
            min_breach = pf.min_qty > 0 and pf.current_qty <= pf.min_qty
            pf.needs_restock = bool(demand_gap or min_breach)

    def action_create_restock_transfer(self):
        """Create internal transfer from Bulk → Pickface to restock.

        Idempotent — skip when an open (non-done, non-cancel) Bulk →
        Pickface transfer for this product+pickface already exists, OR
        when computed restock_qty <= 0.
        """
        self.ensure_one()
        if not self.product_id or not self.location_id:
            return

        existing_open = self.env['stock.move'].sudo().search([
            ('product_id', '=', self.product_id.id),
            ('location_dest_id', '=', self.location_id.id),
            ('state', 'in', ('draft', 'waiting', 'confirmed',
                             'partially_available', 'assigned')),
            ('picking_type_id.code', '=', 'internal'),
        ], limit=1)
        if existing_open:
            return False

        # Find bulk storage location in same warehouse
        warehouse = self.location_id.warehouse_id
        if not warehouse:
            return

        bulk_loc = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('warehouse_id', '=', warehouse.id),
            ('name', 'ilike', 'Stock'),
            ('id', '!=', self.location_id.id),
        ], limit=1)
        if not bulk_loc:
            return

        # Find internal transfer picking type
        int_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', warehouse.id),
        ], limit=1)
        if not int_type:
            return

        qty = self.restock_qty
        if qty <= 0:
            return

        picking = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': bulk_loc.id,
            'location_dest_id': self.location_id.id,
            'origin': _('Restock %s') % self.code,
        })
        self.env['stock.move'].create({
            'description_picking': _('Restock %s → %s') % (
                self.product_id.display_name, self.code),
            'picking_id': picking.id,
            'product_id': self.product_id.id,
            'product_uom_qty': qty,
            'product_uom': self.product_id.uom_id.id,
            'location_id': bulk_loc.id,
            'location_dest_id': self.location_id.id,
        })
        picking.action_confirm()
        picking.action_assign()

        self.message_post(body=_(
            'Restock transfer created: %s (%.0f units from %s)'
        ) % (picking.name, qty, bulk_loc.complete_name))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def _auto_register_product(self, product, location, qty):
        """Auto-create pickface record when product enters PICKFACE location.

        If no wms.zone exists for the warehouse, auto-create a "Default"
        one so the pickface insert doesn't violate the required FK.
        Failures are caught and logged silently so they never break the
        underlying inventory adjustment.
        """
        try:
            if not product or not location:
                return
            existing = self.search([
                ('product_id', '=', product.id),
                ('location_id', '=', location.id),
            ], limit=1)
            if existing:
                return existing

            # Find or auto-create zone for this warehouse
            wh = location.warehouse_id
            if not wh:
                # Walk up parent_path to find a stock.location.warehouse_id
                parent = location.location_id
                while parent and not wh:
                    wh = parent.warehouse_id
                    parent = parent.location_id
            zone = False
            if wh:
                zone = self.env['wms.zone'].search([
                    ('warehouse_id', '=', wh.id),
                ], limit=1)
                if not zone:
                    zone = self.env['wms.zone'].create({
                        'name': f"{wh.name} Default Zone",
                        'code': f"{wh.code}-DEF",
                        'warehouse_id': wh.id,
                    })

            if not zone:
                # No warehouse on the location chain — silently skip
                return

            code = product.default_code or str(product.id)
            min_qty = max(int(qty * 0.2), 1)
            max_qty = max(int(qty * 1.5), 10)

            return self.create({
                'name': 'Pickface %s' % code,
                'code': 'PF-%s' % code,
                'zone_id': zone.id,
                'product_id': product.id,
                'location_id': location.id,
                'min_qty': min_qty,
                'max_qty': max_qty,
            })
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(
                "wms.pickface._auto_register_product skipped: %s", e,
            )
            return

    def action_bulk_restock(self):
        """Create restock transfers for all pickfaces that need it."""
        import logging
        _logger = logging.getLogger(__name__)
        to_restock = self.search([('needs_restock', '=', True)])
        created = 0
        for pf in to_restock:
            try:
                pf.action_create_restock_transfer()
                created += 1
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "Restock failed for pickface %s: %s", pf.code, exc)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Restock'),
                'message': _('Created %d restock transfers.') % created,
                'type': 'success',
            }
        }
