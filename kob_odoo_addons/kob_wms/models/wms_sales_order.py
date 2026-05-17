import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

_logger = logging.getLogger(__name__)


class WmsSalesOrder(models.Model):
    """Matches React `salesOrders` state. One document per platform order that
    must be picked, packed, and handed off to a courier."""
    _name = 'wms.sales.order'
    _description = 'WMS Sales Order (Pick/Pack)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False,
                       readonly=True, default=lambda self: _('New'))
    ref = fields.Char(string='Platform Ref', tracking=True,
                      help='External reference from Shopee/Lazada/TikTok/Odoo')
    customer = fields.Char(string='Customer', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    platform = fields.Selection([
        ('odoo', 'Odoo'),
        ('shopee', 'Shopee'),
        ('lazada', 'Lazada'),
        ('tiktok', 'TikTok'),
        ('pos', 'Point of Sale'),
        ('manual', 'Manual'),
    ], string='Platform', default='manual', tracking=True)
    courier_id = fields.Many2one('wms.courier', string='Courier', tracking=True)
    awb = fields.Char(string='AWB / Tracking', tracking=True)
    box_barcode = fields.Char(string='Box Barcode', tracking=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('picking', 'Picking'),
        ('picked', 'Picked'),
        ('packing', 'Packing'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', tracking=True)

    # SLA breach surfacing — feeds the OUT-scan dispatch list with red /
    # amber decorations that mirror the WMS Pro reference UI.
    sla_state = fields.Selection(
        [('ok', 'On Track'), ('warn', 'Warn'), ('late', 'Late')],
        compute='_compute_sla_state', store=True,
    )
    line_ids = fields.One2many('wms.sales.order.line', 'order_id',
                               string='Items')
    quality_check_ids = fields.One2many('wms.quality.check', 'wms_order_id',
                                        string='Outgoing QC Checks')
    quality_check_count = fields.Integer(
        compute='_compute_qc_count', string='QC Checks')
    quality_check_pending = fields.Integer(
        compute='_compute_qc_count', string='Pending QC')
    picker_id = fields.Many2one('res.users', string='Picker (Odoo User)')
    packer_id = fields.Many2one('res.users', string='Packer (Odoo User)')
    shipper_id = fields.Many2one('res.users', string='Shipper (Odoo User)')
    # WMS portal worker — assigned from kob.wms.user login session
    kob_picker_id = fields.Many2one('kob.wms.user', string='Picker',
                                    index=True, ondelete='set null')
    kob_packer_id = fields.Many2one('kob.wms.user', string='Packer',
                                    index=True, ondelete='set null')

    # Smart Ring timestamps
    sla_start_at = fields.Datetime(string='SLA Start (Print Pick List)')
    pick_start_at = fields.Datetime(string='Pick Start')
    picked_at = fields.Datetime(string='Pick End')
    pack_start_at = fields.Datetime(string='Pack Start')
    packed_at = fields.Datetime(string='Pack End')
    shipped_at = fields.Datetime(string='Shipped At')

    # Cancel + Return audit trail
    # - cancelled_at  : set when status → 'cancelled' (any path)
    # - cancelled_by_id : Odoo user who triggered the cancel
    # - returned_at   : set when warehouse worker scans in Return mode
    # - returned_by_id : kob.wms.user (warehouse worker) who scanned
    cancelled_at = fields.Datetime(string='Cancelled At', readonly=True,
                                   tracking=True)
    cancelled_by_id = fields.Many2one('res.users', string='Cancelled By',
                                       readonly=True, tracking=True)
    returned_at = fields.Datetime(string='Returned At', readonly=True,
                                   tracking=True)
    returned_by_id = fields.Many2one('kob.wms.user', string='Returned By',
                                       readonly=True, tracking=True)

    # Smart Ring error counts
    pick_errors = fields.Integer(string='Pick Errors', default=0)
    pack_errors = fields.Integer(string='Pack Errors', default=0)

    # ── Audit Hash (Blockchain-style tamper detection w/ Boat recovery) ─
    # Sealed at terminal status transitions (packed/shipped/cancelled/returned).
    # 3-way compare on UI: sealed vs current vs boat-live.
    # Postgres AFTER UPDATE trigger catches silent psql tampering.
    audit_hash = fields.Char(
        string='Audit Hash', readonly=True, copy=False, index=True,
        help='SHA-256 fingerprint of order+lines snapshot at terminal '
             'status transition. Mismatch with recompute = tampering.')
    audit_hash_at = fields.Datetime(string='Sealed At', readonly=True, copy=False)
    audit_hash_user_id = fields.Many2one(
        'res.users', string='Sealed By', readonly=True, copy=False)
    audit_hash_version = fields.Integer(
        string='Hash Schema Version', default=1, readonly=True,
        help='Snapshot schema version. Bump when _compute_audit_snapshot '
             'changes; old hashes need re-seal under new version.')
    audit_hash_source = fields.Selection([
        ('realtime', 'Realtime (at seal)'),
        ('backfill', 'Backfill (post-hoc)'),
        ('recovery', 'Recovery (re-synced from Boat)'),
    ], string='Hash Source', readonly=True, copy=False, default='realtime')

    # Smart Ring computed durations
    wait_pick_min = fields.Float(compute='_compute_durations', store=True,
                                  help='Wait: SLA start → Pick start')
    pick_duration_min = fields.Float(compute='_compute_durations', store=True,
                                      help='Pick: first scan → all picked')
    wait_pack_min = fields.Float(compute='_compute_durations', store=True,
                                  help='Wait: Pick end → Pack start')
    pack_duration_min = fields.Float(compute='_compute_durations', store=True,
                                      help='Pack: first scan → box closed')
    wait_ship_min = fields.Float(compute='_compute_durations', store=True,
                                  help='Wait: Pack end → Ship')
    ship_duration_min = fields.Float(compute='_compute_durations', store=True)
    total_duration_min = fields.Float(compute='_compute_durations', store=True,
                                      help='Total: SLA start → Shipped')

    # Difficulty metrics
    items_count = fields.Integer(compute='_compute_difficulty', store=True)
    sku_count = fields.Integer(compute='_compute_difficulty', store=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    # --- Multi-order pick group linkage ---
    pick_group_id = fields.Many2one(
        'wms.pick.group', string='Pick Group',
        ondelete='set null', index=True, tracking=True,
        help='Multi-order pick set this SO belongs to. Status promotion to '
             '"picked"/"packed" is gated until ALL members in group complete. '
             'Standalone SOs (no group) keep legacy single-order behavior.')

    # --- Core Odoo integration ---
    sale_order_id = fields.Many2one('sale.order', string='Sale Order',
                                    tracking=True, ondelete='set null')
    # Sale order's display name — what the WMS Pick/Pack/Outbound queue
    # tables show in the "Order" column (instead of the internal
    # ``wms.sales.order.name`` sequence). Falls back to the WMS sequence
    # when there's no linked sale.order (manual/POS originated rows).
    so_name = fields.Char(string='Sale Order Number',
                          related='sale_order_id.name',
                          store=True, readonly=True)
    sale_order_date = fields.Datetime(string='Order Date',
                                       related='sale_order_id.date_order',
                                       store=True, readonly=True,
                                       help='Date the sale order was placed '
                                            '(date_order on linked SO).')
    # What WMS list views render in their "Order" column. Falls back to
    # the internal sequence ``name`` when no sale.order is linked
    # (manual / POS-originated rows).
    display_order_name = fields.Char(
        string='Order',
        compute='_compute_display_order_name',
        store=True, index=True,
    )

    @api.depends('so_name', 'name')
    def _compute_display_order_name(self):
        for rec in self:
            rec.display_order_name = rec.so_name or rec.name or ''

    # === SLA breach (per WMS Pro reference: 48h Shopee/Lazada, 72h
    # TikTok, 24h Odoo/manual). Late = past deadline; Warn = >80% used.
    _PLATFORM_SLA_HOURS = {
        'shopee': 48, 'lazada': 48, 'tiktok': 72,
        'odoo': 24, 'pos': 24, 'manual': 24,
    }

    @api.depends('create_date', 'platform', 'status')
    def _compute_sla_state(self):
        now = fields.Datetime.now()
        for so in self:
            if so.status in ('shipped', 'cancelled') or not so.create_date:
                so.sla_state = 'ok'
                continue
            sla_h = self._PLATFORM_SLA_HOURS.get(so.platform or '', 24)
            elapsed_h = (now - so.create_date).total_seconds() / 3600
            if elapsed_h > sla_h:
                so.sla_state = 'late'
            elif elapsed_h > sla_h * 0.8:
                so.sla_state = 'warn'
            else:
                so.sla_state = 'ok'

    def _kob_bin_hint(self):
        """Pack bin metadata + voice prompt for the OUT scan UI.

        Falls back to a sane default when the courier has no bin metadata
        (e.g. KISS in-house deliveries) so the OWL bin-hint card always
        renders something useful.
        """
        self.ensure_one()
        courier = self.courier_id
        return {
            'bin': courier.bin_number or 6,
            'color': courier.bin_color or '#2563eb',
            'label': (courier.name or 'KISS') if courier else 'KISS',
            'voice': (
                courier.voice_label or courier.name or ''
            ) if courier else '',
            'all_picked': self.all_picked,
            'all_packed': self.all_packed,
            'sla_state': self.sla_state,
        }
    picking_id = fields.Many2one('stock.picking', string='Delivery Order',
                                 tracking=True, ondelete='set null')

    expected_total = fields.Integer(compute='_compute_totals', store=True)
    picked_total = fields.Integer(compute='_compute_totals', store=True)
    packed_total = fields.Integer(compute='_compute_totals', store=True)
    count_value = fields.Integer(
        string='Count Helper', default=1, readonly=True,
        help='Always 1, used as a pivot count measure in dashboards.')
    all_picked = fields.Boolean(compute='_compute_totals', store=True)
    all_packed = fields.Boolean(compute='_compute_totals', store=True)

    # --- SLA tracking ---
    sla_pick_deadline = fields.Datetime(
        compute='_compute_sla', store=True, string='Pick SLA Deadline')
    sla_pack_deadline = fields.Datetime(
        compute='_compute_sla', store=True, string='Pack SLA Deadline')
    sla_ship_deadline = fields.Datetime(
        compute='_compute_sla', store=True, string='Ship SLA Deadline')
    sla_status = fields.Selection([
        ('on_track', '✅ On Track'),
        ('at_risk', '⚠️ At Risk'),
        ('breached', '🔴 Breached'),
        ('done', '✓ Done'),
    ], string='SLA Status', compute='_compute_sla', store=True)

    # ── Box / Cartonization Analytics ────────────────────────────────────────
    actual_box_id = fields.Many2one(
        'wms.box.size', string='Box Used',
        compute='_compute_actual_box', store=True, index=True,
        help='Resolved from box_barcode → matches wms.box.size.code')
    suggested_box_id = fields.Many2one(
        'wms.box.size', string='AI Suggested Box',
        index=True, ondelete='set null',
        help='Box recommended by the AI cartonization algorithm')
    order_vol_m3 = fields.Float(
        string='Order Volume (m³)',
        compute='_compute_order_dims', store=True, digits=(12, 6),
        help='Sum of product.volume × picked_qty for all lines')
    order_weight_kg = fields.Float(
        string='Order Weight (kg)',
        compute='_compute_order_dims', store=True, digits=(10, 3),
        help='Sum of product.weight × picked_qty for all lines')
    box_fill_pct = fields.Float(
        string='Box Fill %',
        compute='_compute_box_analytics', store=True, digits=(5, 1),
        help='order_vol_m3 / actual box volume × 100')
    box_cost_est = fields.Float(
        string='Box Cost (฿)',
        compute='_compute_box_analytics', store=True, digits=(10, 2),
        help='Unit cost of the actual box used')
    tape_cost_est = fields.Float(
        string='Tape Cost (฿)',
        compute='_compute_box_analytics', store=True, digits=(10, 2),
        help='Estimated tape cost: [(W+H)×2 × rounds + overlap] ÷ 100 × ฿/m')
    bubble_cost_est = fields.Float(
        string='Bubble Wrap Cost (฿)',
        compute='_compute_box_analytics', store=True, digits=(10, 2),
        help='Bubble wrap material cost estimate for this box size')
    total_pack_cost = fields.Float(
        string='Total Pack Cost (฿)',
        compute='_compute_box_analytics', store=True, digits=(10, 2),
        help='Box + Tape + Bubble Wrap — total packaging material cost per order')
    box_suggestion_hit = fields.Boolean(
        string='AI Hit',
        compute='_compute_box_analytics', store=True,
        help='True when packer chose the AI-suggested box')

    @api.depends('quality_check_ids', 'quality_check_ids.state')
    def _compute_qc_count(self):
        for o in self:
            o.quality_check_count = len(o.quality_check_ids)
            o.quality_check_pending = len(o.quality_check_ids.filtered(
                lambda q: q.state == 'pending'))

    @api.depends('box_barcode')
    def _compute_actual_box(self):
        BoxSize = self.env['wms.box.size']
        for o in self:
            if o.box_barcode:
                box = BoxSize.search(
                    [('code', '=', o.box_barcode), ('active', '=', True)],
                    limit=1)
                o.actual_box_id = box
            else:
                o.actual_box_id = False

    @api.depends('line_ids.picked_qty', 'line_ids.product_id',
                 'line_ids.product_id.volume', 'line_ids.product_id.weight')
    def _compute_order_dims(self):
        for o in self:
            vol = 0.0
            wgt = 0.0
            for line in o.line_ids:
                qty = line.picked_qty or 0
                if qty and line.product_id:
                    if line.product_id.volume:
                        vol += line.product_id.volume * qty
                    if line.product_id.weight:
                        wgt += line.product_id.weight * qty
            o.order_vol_m3 = vol
            o.order_weight_kg = wgt

    @api.depends('actual_box_id', 'suggested_box_id', 'order_vol_m3',
                 'actual_box_id.volume', 'actual_box_id.unit_cost',
                 'actual_box_id.tape_cost_est', 'actual_box_id.bubble_cost_est',
                 'actual_box_id.total_material_cost')
    def _compute_box_analytics(self):
        for o in self:
            box = o.actual_box_id
            if box and o.order_vol_m3 > 0 and box.volume > 0:
                o.box_fill_pct = round(o.order_vol_m3 / box.volume * 100, 1)
            else:
                o.box_fill_pct = 0.0
            o.box_cost_est    = box.unit_cost       if box else 0.0
            o.tape_cost_est   = box.tape_cost_est   if box else 0.0
            o.bubble_cost_est = box.bubble_cost_est if box else 0.0
            o.total_pack_cost = box.total_material_cost if box else 0.0
            o.box_suggestion_hit = bool(
                box and o.suggested_box_id
                and box.id == o.suggested_box_id.id)

    @api.depends('line_ids.expected_qty', 'line_ids.picked_qty',
                 'line_ids.packed_qty')
    def _compute_totals(self):
        for order in self:
            order.expected_total = sum(order.line_ids.mapped('expected_qty'))
            order.picked_total = sum(order.line_ids.mapped('picked_qty'))
            order.packed_total = sum(order.line_ids.mapped('packed_qty'))
            order.all_picked = (order.expected_total > 0
                                and order.picked_total >= order.expected_total)
            order.all_packed = (order.all_picked
                                and order.packed_total >= order.picked_total)

    @api.depends('create_date', 'sla_start_at', 'picked_at', 'packed_at',
                 'shipped_at', 'status', 'platform')
    def _compute_sla(self):
        Config = self.env['wms.sla.config'].sudo()
        now = fields.Datetime.now()
        for order in self:
            cfg = Config.get_for_platform(order.platform)
            # SLA starts from print pick list (sla_start_at), fallback to create_date
            base = order.sla_start_at or order.create_date or now
            order.sla_pick_deadline = base + timedelta(
                minutes=cfg.pick_sla_minutes if cfg else 120)
            pack_base = order.picked_at or order.sla_pick_deadline
            order.sla_pack_deadline = pack_base + timedelta(
                minutes=cfg.pack_sla_minutes if cfg else 60)
            ship_base = order.packed_at or order.sla_pack_deadline
            order.sla_ship_deadline = ship_base + timedelta(
                minutes=cfg.ship_sla_minutes if cfg else 240)

            if order.status in ('shipped', 'cancelled'):
                order.sla_status = 'done'
            else:
                if order.status in ('pending', 'picking'):
                    deadline = order.sla_pick_deadline
                elif order.status in ('picked', 'packing'):
                    deadline = order.sla_pack_deadline
                else:
                    deadline = order.sla_ship_deadline
                remaining = (deadline - now).total_seconds() / 60
                if remaining < 0:
                    order.sla_status = 'breached'
                elif remaining < 30:
                    order.sla_status = 'at_risk'
                else:
                    order.sla_status = 'on_track'

    @api.depends('sla_start_at', 'pick_start_at', 'picked_at',
                 'pack_start_at', 'packed_at', 'shipped_at', 'platform')
    def _compute_durations(self):
        SlaConfig = self.env['wms.sla.config'].sudo()
        for o in self:
            cfg = SlaConfig.get_for_platform(o.platform or 'default')

            def _net(a, b):
                if not a or not b:
                    return 0.0
                if cfg:
                    return cfg.net_working_minutes(a, b)
                return round((b - a).total_seconds() / 60, 1)

            base = o.sla_start_at or o.create_date
            o.wait_pick_min     = _net(base, o.pick_start_at)
            o.pick_duration_min = _net(o.pick_start_at, o.picked_at)
            o.wait_pack_min     = _net(o.picked_at, o.pack_start_at)
            o.pack_duration_min = _net(o.pack_start_at, o.packed_at)
            o.wait_ship_min     = _net(o.packed_at, o.shipped_at)
            o.ship_duration_min = 0
            o.total_duration_min = _net(base, o.shipped_at)

    @api.depends('line_ids.expected_qty')
    def _compute_difficulty(self):
        for o in self:
            o.items_count = sum(o.line_ids.mapped('expected_qty'))
            o.sku_count = len(o.line_ids)

    def action_print_picklist(self):
        """Admin prints pick list → starts SLA timer."""
        now = fields.Datetime.now()
        for order in self:
            if not order.sla_start_at:
                order.sla_start_at = now
                order.message_post(body=_('SLA timer started — Pick List printed.'))
        # Return print action
        return self.env.ref('kob_wms.action_report_wms_pick_list').report_action(self)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'wms.sales.order') or _('New')
        records = super().create(vals_list)
        # Bump today's daily report so the dashboard reflects the new
        # order immediately, not at next cron tick.
        self.env['wms.daily.report'].sudo().refresh_today()
        return records

    def write(self, vals):
        """Refresh today's daily report whenever status changes so live
        dashboard numbers (shipped / pending / cancelled) stay accurate
        without waiting for the cron tick."""
        res = super().write(vals)
        if 'status' in vals:
            self.env['wms.daily.report'].sudo().refresh_today()
        return res

    # ------------------------------------------------------------------
    # Stock integration helpers (strict — no best-effort)
    # ------------------------------------------------------------------
    def _ensure_picking_reserved(self):
        """Confirm + reserve the linked picking. Returns error string or None."""
        self.ensure_one()
        if not self.picking_id:
            return _('No delivery order linked.')
        picking = self.picking_id
        if picking.state == 'done':
            return None  # already done, OK
        if picking.state == 'cancel':
            return _('Delivery %s is cancelled.') % picking.name
        if picking.state == 'draft':
            picking.action_confirm()
        if picking.state in ('confirmed', 'waiting'):
            picking.action_assign()
        # Check reservation status — return error string, don't raise
        if picking.state != 'assigned':
            unreserved = picking.move_ids.filtered(
                lambda m: m.state not in ('assigned', 'done', 'cancel'))
            if unreserved:
                products = ', '.join(unreserved.mapped('product_id.display_name'))
                return _(
                    'Cannot reserve stock for %s. Products: %s. Location: %s'
                ) % (picking.name, products, picking.location_id.complete_name)
        return None

    def _get_demand_map(self):
        """Build demand map from stock.picking move_lines.
        Returns {product_id: {lot_id: remaining_demand_qty}}"""
        self.ensure_one()
        if not self.picking_id:
            return {}
        demand = {}
        for ml in self.picking_id.move_line_ids:
            pid = ml.product_id.id
            lot_id = ml.lot_id.id if ml.lot_id else 0
            reserved = ml.quantity_product_uom or 0
            done = ml.quantity or 0
            remaining = reserved - done
            if remaining <= 0:
                continue
            demand.setdefault(pid, {})[lot_id] = (
                demand.get(pid, {}).get(lot_id, 0) + remaining)
        return demand

    @staticmethod
    def _norm_code(s):
        """Normalise a scanned/stored code for comparison.

        Strips:
        - surrounding whitespace
        - one trailing ``.`` or ``.0`` suffix (Excel/CSV float→string artifact
          where a barcode stored as a number gets serialised with a decimal
          point; e.g. ``8859139108017.`` or ``8859139108017.0`` should match
          a scan of ``8859139108017``)

        DOES NOT touch trailing digits — that would corrupt legitimate
        barcodes ending in ``0`` (e.g. ``100`` must NOT become ``1``).

        Result is uppercased for case-insensitive comparison.
        """
        if not s:
            return ""
        v = str(s).strip()
        # Match exactly: trailing `.` or `.0` (but NOT `.123`)
        if v.endswith(".0"):
            v = v[:-2]
        elif v.endswith("."):
            v = v[:-1]
        return v.upper()

    def _find_line_by_code(self, code):
        """Match a wms.sales.order.line by sku, default_code, or barcode.
        Match is case-insensitive and tolerant of trailing dot/zero noise.
        """
        norm = self._norm_code(code)
        def _match(l):
            if l.picked_qty >= l.expected_qty:
                return False
            if l.sku and self._norm_code(l.sku) == norm:
                return True
            if l.product_id:
                if l.product_id.default_code and self._norm_code(l.product_id.default_code) == norm:
                    return True
                if l.product_id.barcode and self._norm_code(l.product_id.barcode) == norm:
                    return True
            return False
        return self.line_ids.filtered(_match)[:1]

    def _diagnose_scan_miss(self, code):
        """Return a more useful error message when a scan fails to match any
        line. Differentiates:
        - product unknown in DB
        - product known but not in this order
        - product in order but already fully picked
        """
        norm = self._norm_code(code)
        if not norm:
            return _('Empty scan')
        # Lookup product by sku/default_code/barcode anywhere in DB.
        # Use both raw and norm forms to cover dirty imports (trailing dots).
        Product = self.env['product.product']
        candidates = (
            Product.search([('default_code', '=ilike', code)], limit=5)
            | Product.search([('default_code', '=ilike', norm)], limit=5)
            | Product.search([('barcode', '=ilike', code)], limit=5)
            | Product.search([('barcode', '=ilike', norm)], limit=5)
            | Product.search([('barcode', '=ilike', norm + '.')], limit=5)
            | Product.search([('barcode', '=ilike', norm + '.0')], limit=5)
        )
        # Pick whichever matches after normalisation
        product = candidates.filtered(
            lambda p: self._norm_code(p.default_code) == norm
                   or self._norm_code(p.barcode) == norm
        )[:1]
        if not product:
            return _('ไม่พบสินค้า "%s" ในระบบ (SKU/Barcode ไม่ถูกต้อง)') % code
        # Product exists — check if in this order
        line_in_order = self.line_ids.filtered(lambda l: l.product_id == product)
        if not line_in_order:
            return _('สินค้า "%s" (%s) ไม่อยู่ใน order นี้') % (
                product.default_code or product.name, code)
        # In order but already fully picked
        return _('"%s" pick ครบแล้ว (%d/%d)') % (
            product.default_code or product.name,
            line_in_order[0].picked_qty,
            line_in_order[0].expected_qty,
        )

    def _find_move_line(self, product, lot=None):
        """Find the exact stock.move.line to update for this product+lot.
        Strict match — returns None if nothing available."""
        if not self.picking_id:
            return None
        # Priority 1: match product + lot + has remaining demand
        if lot:
            ml = self.picking_id.move_line_ids.filtered(
                lambda m: m.product_id == product
                and m.lot_id == lot
                and (m.quantity or 0) < (m.quantity_product_uom or 0)
            )[:1]
            if ml:
                return ml
        # Priority 2: match product + no lot filter + has remaining demand
        ml = self.picking_id.move_line_ids.filtered(
            lambda m: m.product_id == product
            and (m.quantity or 0) < (m.quantity_product_uom or 0)
        )[:1]
        return ml or None

    def _resolve_lot(self, code, product):
        """Check if code is a Lot/Serial barcode for this product."""
        if not product or product.tracking == 'none':
            return None, False
        lot = self.env['stock.lot'].search([
            ('name', '=', code),
            ('product_id', '=', product.id),
        ], limit=1)
        return (lot, True) if lot else (None, False)

    def _get_fefo_lot(self, product, location):
        """Get the lot with earliest expiry date that has stock at location (FEFO)."""
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
            ('lot_id', '!=', False),
            ('quantity', '>', 0),
        ])
        if not quants:
            return None
        # Sort by lot expiration_date (earliest first), filter out expired
        lots_with_expiry = []
        for q in quants:
            lot = q.lot_id
            if lot.expiration_date:
                lots_with_expiry.append((lot.expiration_date, lot))
            else:
                lots_with_expiry.append((fields.Datetime.now() + timedelta(days=9999), lot))
        if not lots_with_expiry:
            return quants[0].lot_id  # fallback: any lot
        lots_with_expiry.sort(key=lambda x: x[0])  # earliest first
        return lots_with_expiry[0][1]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _auto_complete_service_lines(self, phase='pick'):
        """Auto-fill picked_qty / packed_qty for fee/service lines.
        Called after each physical item scan so service lines never block progress.
        phase='pick'  → set picked_qty = expected_qty
        phase='pack'  → set packed_qty = picked_qty (or expected_qty if 0)
        """
        for line in self.line_ids.filtered('is_service'):
            if phase == 'pick' and line.picked_qty < line.expected_qty:
                line.picked_qty = line.expected_qty
            elif phase == 'pack' and line.packed_qty < (line.picked_qty or line.expected_qty):
                line.packed_qty = line.picked_qty or line.expected_qty

    # ------------------------------------------------------------------
    # Count-lock helper
    # ------------------------------------------------------------------
    def _count_lock_msg(self):
        """Return error message if any picking location is being counted, else None."""
        self.ensure_one()
        if not self.picking_id:
            return None
        for move in self.picking_id.move_ids:
            for loc in (move.location_id, move.location_dest_id):
                if loc.counting_task_id:
                    return _(
                        '🔒 Location "%s" is currently being counted (Task: %s).\n'
                        'Please finish the count task before scanning this order.'
                    ) % (loc.display_name, loc.counting_task_id.name)
        return None

    # ------------------------------------------------------------------
    # Scan workflows
    # ------------------------------------------------------------------
    def scan_pick(self, sku, kob_worker_id=None):
        """Pick one unit. Checks: delivery assigned + qty. Logs errors."""
        self.ensure_one()
        if kob_worker_id:
            self = self.with_context(kob_worker_id=kob_worker_id)

        def _err(msg):
            self.pick_errors = (self.pick_errors or 0) + 1
            self._log_action('error_pick', sku or '', note=msg)
            return {'ok': False, 'error': msg}

        # 0. Cancelled guard — block pickers from wasting time on dead
        #    orders. Show when it was cancelled so picker can hand the
        #    order over to the Return queue.
        if self.status == 'cancelled':
            when = fields.Datetime.to_string(self.cancelled_at) \
                if self.cancelled_at else _('unknown time')
            return _err(_(
                '⚠ ORDER CANCELLED at %s — do not pick. '
                'Move to Return queue.'
            ) % when)

        # 1. Must have delivery
        if not self.picking_id:
            return _err(_('No delivery linked to %s.') % (self.ref or self.name))

        # 1b. Count lock — block pick if source location is being counted
        lock_msg = self._count_lock_msg()
        if lock_msg:
            return _err(lock_msg)

        # 2. Ensure delivery is reserved (all items must be available)
        picking = self.picking_id
        if picking.state == 'cancel':
            return _err(_('Delivery %s is cancelled.') % picking.name)
        if picking.state == 'draft':
            picking.action_confirm()
        if picking.state in ('confirmed', 'waiting'):
            picking.action_assign()
        if picking.state != 'assigned':
            not_avail = picking.move_ids.filtered(
                lambda m: m.state not in ('assigned', 'done', 'cancel'))
            missing = ', '.join(
                '%s (%.0f)' % (m.product_id.default_code or m.product_id.display_name,
                               m.product_uom_qty)
                for m in not_avail)
            return _err(_(
                'Not all items available — cannot pick.\n'
                'Missing: %s\n'
                'Location: %s'
            ) % (missing, picking.location_id.complete_name))

        # 2b. Guard: picking is "assigned" but reserved qty may be 0 (e.g. after
        #     a cycle count adjustment unreserved the stock between order creation
        #     and scanning).  Re-verify actual reserved qty on move lines.
        total_reserved = sum(
            ml.quantity_product_uom for ml in picking.move_line_ids)
        if total_reserved == 0:
            return _err(_(
                '⚠️ สต็อคสำรองหาย (Delivery %s ไม่มี reserved qty)\n'
                'กรุณาตรวจสอบ Inventory → %s ว่ามีสินค้าพร้อมส่งหรือไม่'
            ) % (picking.name, picking.location_id.complete_name))

        # 3. Find WMS line (case-insensitive)
        line = self._find_line_by_code(sku)
        lot = None
        if not line:
            for l in self.line_ids.filtered(lambda x: x.picked_qty < x.expected_qty):
                if l.product_id and l.product_id.tracking != 'none':
                    found_lot, _lot_msg = self._resolve_lot(sku, l.product_id)
                    if found_lot:
                        line = l
                        lot = found_lot
                        break

        if not line:
            return _err(self._diagnose_scan_miss(sku))

        product = line.product_id
        if not product:
            return _err(_('No product linked: %s') % line.sku)

        # 4. Check qty — don't exceed expected
        if line.picked_qty >= line.expected_qty:
            return _err(_('Already fully picked: %s (%d/%d)') % (
                sku, line.picked_qty, line.expected_qty))

        # 4b. Per-product availability gate — block scan if THIS specific
        # product has 0 reserved qty on the linked picking. Without this,
        # the user can scan a barcode that maps to a product whose stock
        # vanished after the picking was confirmed (cycle-count adjustment,
        # cross-warehouse transfer, manual unreserve), and Odoo silently
        # creates a 0-qty pick that blows up at validate time.
        product_reserved = sum(
            ml.quantity_product_uom for ml in picking.move_line_ids
            if ml.product_id.id == product.id
        )
        if product_reserved <= 0:
            on_hand = self.env['stock.quant']._get_available_quantity(
                product, picking.location_id,
            )
            return _err(_(
                '🚫 สินค้าไม่พร้อมหยิบ (Out of Stock)\n'
                'SKU: %(sku)s\n'
                'Product: %(name)s\n'
                'Reserved: 0 — On-hand at %(loc)s: %(qty).0f\n'
                'แก้ไข: ตรวจ Inventory แล้ว Re-assign delivery %(pick)s '
                'หรือเติม stock ก่อนสแกน'
            ) % {
                'sku': sku,
                'name': product.display_name,
                'loc': picking.location_id.complete_name,
                'qty': on_hand,
                'pick': picking.name,
            })

        # 5. WMS only tracks picked_qty — does NOT touch delivery move_line
        # Odoo delivery handles qty/lot/reserve automatically
        # WMS validates completeness at close_box → then calls delivery validate
        line.picked_qty += 1
        # Auto-complete fee/service lines so they never block picking progress
        self._auto_complete_service_lines(phase='pick')
        now = fields.Datetime.now()
        if not self.picker_id:
            self.picker_id = self.env.user
        if not self.pick_start_at:
            self.pick_start_at = now
        self.status = 'picking'
        self._log_action('pick', sku, kob_user_id=self._context.get('kob_worker_id'))
        # Set WMS picker (kob.wms.user) if provided via context
        kob_wid = self._context.get('kob_worker_id')
        if kob_wid and not self.kob_picker_id:
            self.kob_picker_id = kob_wid

        if self.all_picked:
            self.picked_at = now
            if self.pick_group_id:
                # Multi-order group: only promote when ALL siblings done.
                if self.pick_group_id.group_picked:
                    siblings = self.pick_group_id.order_ids.filtered(
                        lambda o: o.status in ('picking', 'pending'))
                    siblings.write({'status': 'picked', 'picked_at': now})
                    self.pick_group_id.state = 'picked'
                    # Skip-Pack: autopack each sibling as well
                    for sib in siblings:
                        if (sib.all_picked
                                and getattr(sib.company_id or self.env.company,
                                            'wms_skip_pack', False)):
                            try:
                                sib._kob_skip_pack_autopack()
                            except Exception:
                                _logger.exception(
                                    "skip_pack autopack failed for sibling %s",
                                    sib.name)
                else:
                    # Stay 'picking' until siblings complete.
                    self.pick_group_id.state = 'picking'
            else:
                self.status = 'picked'
        elif self.pick_group_id and self.pick_group_id.state == 'open':
            self.pick_group_id.state = 'picking'

        # ── Skip-Pack mode: auto-flip picked → packed at PICK completion ──
        # When res.company.wms_skip_pack is enabled, the warehouse skips
        # the dedicated Pack station. As soon as Pick is fully done, mirror
        # picked_qty into packed_qty, validate stock, post invoice, set a
        # default box, and stamp status='packed' so the SO appears on the
        # OUT screen ready for AWB scan.
        if (self.status == 'picked'
                and self.all_picked
                and getattr(self.company_id or self.env.company,
                            'wms_skip_pack', False)):
            try:
                self._kob_skip_pack_autopack()
            except Exception:
                _logger.exception(
                    "skip_pack autopack failed at scan_pick for %s", self.name)

        bin_hint = self._kob_bin_hint()
        spoken = (f"ครบแล้ว {bin_hint['voice']}".strip()
                  if self.all_picked else f"ชิ้นที่ {line.picked_qty}")
        return {'ok': True, 'bin_hint': bin_hint, 'spoken_text': spoken}

    def _kob_skip_pack_autopack(self):
        """Run Pack's work inline so SO advances to status='packed'.

        Called when wms_skip_pack is enabled on the SO's company AND the
        order is fully picked. Mirrors picked → packed quantities, picks a
        default box (suggested → smallest active), validates stock,
        creates the invoice, and stamps packed_at + status='packed'.
        Idempotent: already-packed orders short-circuit.
        """
        self.ensure_one()
        if self.status not in ('picked', 'picking', 'packing'):
            return
        if not self.all_picked:
            return
        # Mirror picked_qty into packed_qty so reports tie out
        for line in self.line_ids:
            if (line.packed_qty or 0) < (line.picked_qty or 0):
                line.packed_qty = line.picked_qty
        # Auto-assign a default box if none chosen yet
        if not self.actual_box_id and not self.box_barcode:
            default_box = self.suggested_box_id
            if not default_box:
                default_box = self.env['wms.box.size'].search(
                    [('active', '=', True)],
                    order='volume_cm3 asc', limit=1)
            if default_box:
                self.box_barcode = default_box.code
        # Cut stock through the picking (idempotent inside _validate_picking)
        if self.picking_id:
            stock_errors = self._validate_picking()
            if stock_errors:
                _logger.warning(
                    "skip_pack autopack: stock issues on %s — %s",
                    self.name, stock_errors[0])
                return
        # Post invoice (best-effort)
        try:
            self._auto_create_invoice()
        except Exception:
            _logger.exception(
                "skip_pack autopack: invoice post failed for %s", self.name)
        self.status = 'packed'
        self.packed_at = fields.Datetime.now()
        self._log_action(
            'skip_pack', self.ref or self.name,
            note='Pack stage auto-skipped at PICK completion '
                 '— invoice + stock + auto-box handled inline')

    # ------------------------------------------------------------------
    # Queue-level multi-order scan dispatcher (F1 basket mode)
    # ------------------------------------------------------------------
    @api.model
    def resolve_so_ref(self, code):
        """Public RPC wrapper for `_resolve_so_ref`.

        Returns the wms.sales.order id matching `code`, or False.
        Used by the scan-bar widget to detect SO refs vs product codes.
        """
        rec = self._resolve_so_ref(code)
        return rec.id if rec else False

    @api.model
    def _resolve_so_ref(self, code):
        """Resolve a barcode to a wms.sales.order by name/ref/so_name or
        by sale.order.name / client_order_ref. Returns empty recordset
        if not matched.

        When the scanned ref maps to a sale.order that is still in
        Quotation state (``draft``/``sent``), the SO is auto-confirmed
        and a wms.sales.order is created on the fly so workers can
        proceed with Pick without going back to the back-office.
        """
        code = (code or '').strip()
        if not code:
            return self.browse()
        # Try the WMS sequence (e.g. WMS/2026/0001)
        rec = self.search([('name', '=', code)], limit=1)
        if rec:
            return rec
        # Try the platform ref
        rec = self.search([('ref', '=', code)], limit=1)
        if rec:
            return rec
        # Try the linked sale.order name (e.g. SO0042)
        rec = self.search([('so_name', '=', code)], limit=1)
        if rec:
            return rec
        # Match on sale.order: name OR client_order_ref (marketplace ref).
        # Restrict to companies the current user is allowed to see so a
        # cross-company duplicate ref doesn't surface the wrong row.
        company_ids = self.env.companies.ids or [self.env.company.id]
        sale = self.env['sale.order'].sudo().search([
            '|', ('name', '=', code), ('client_order_ref', '=', code),
            ('company_id', 'in', company_ids),
        ], limit=1)
        if sale:
            rec = self.search([('sale_order_id', '=', sale.id)], limit=1)
            if rec:
                return rec
            # No wms row yet — bridge it now (auto-confirm if Quotation).
            return self._auto_bridge_sale_order(sale)
        return self.browse()

    @api.model
    def _auto_bridge_sale_order(self, sale):
        """Confirm a Quotation-state sale.order on first scan and create
        the matching wms.sales.order so Pick/Pack screens see it.

        Mirrors ``marketplace_import_wizard``'s auto_confirm+WMS-bridge
        path so SOs that came in as draft (rds_state='draft' or whose
        wizard import skipped confirm) become pickable as soon as a
        worker scans the ref. Idempotent — a row that already exists
        is returned unchanged.

        Policy: allow Pick for any non-cancel state. Cancel = blocked.
        Draft/sent attempts auto-confirm; if confirm fails the bridge
        still proceeds when stock.picking already exists (admin may
        have printed a pick list manually).
        """
        so = sale.sudo()
        # Already bridged → just return it.
        rec = self.search([('sale_order_id', '=', so.id)], limit=1)
        if rec:
            return rec
        # Hard block: cancel.
        if so.state == 'cancel':
            return self.browse()
        # Try to confirm draft/sent so stock.picking is generated.
        if so.state in ('draft', 'sent'):
            try:
                so.with_company(so.company_id).action_confirm()
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "Scan-time auto-confirm failed for %s: %s",
                    so.name, exc,
                )
                # Fall through — bridge anyway if pickings exist.
        # Bridge if there is at least one non-cancel picking to attach to.
        pickings = so.picking_ids.filtered(lambda p: p.state != 'cancel')
        if not pickings:
            return self.browse()
        for picking in pickings:
            try:
                picking.with_company(so.company_id).action_assign()
            except Exception:  # noqa: BLE001
                pass
            if picking.wms_sales_order_ids:
                continue
            try:
                picking.with_company(so.company_id).action_create_wms_order()
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "Scan-time WMS bridge failed for %s: %s",
                    picking.name, exc,
                )
        return self.search([('sale_order_id', '=', so.id)], limit=1)

    @api.model
    def queue_scan_dispatch(self, active_order_ids, code, kob_worker_id=None,
                            burst=False):
        """Queue-level multi-order scan orchestrator.

        Behaviour:
          - barcode resolves to a wms.sales.order  → add to Active basket
          - barcode resolves to a product          → distribute to first
            order in the basket (FIFO by sale_order_date) that still
            needs the SKU; delegate to existing ``scan_pick`` so all
            stock + qty + log + status rules apply unchanged
          - no match                               → error

        Args:
            active_order_ids (list[int]): wms.sales.order ids currently
                in the worker's basket (empty list means basket is empty).
            code (str): scanned barcode.
            kob_worker_id (int|None): kob.wms.user id for activity log.

        Returns dict with one of:
            {type: 'so_added',     order_id, order_name}
            {type: 'so_duplicate', order_id, order_name}
            {type: 'so_invalid',   error}
            {type: 'pick',         order_id, order_name, line_id,
                                   product_name,
                                   all_picked_in_order,
                                   all_done_in_basket}
            {type: 'error',        error}
        """
        code = (code or '').strip()
        if not code:
            return {'type': 'error', 'error': _('Empty scan')}
        active_order_ids = [int(i) for i in (active_order_ids or [])]

        # 1) Try to resolve as a sales-order ref first (cheap, exact match)
        so = self._resolve_so_ref(code)
        if so:
            if so.id in active_order_ids:
                return {'type': 'so_duplicate',
                        'order_id': so.id,
                        'order_name': so.display_order_name or so.name}
            # Policy: Pick allowed on every status EXCEPT cancelled.
            # Admin prints pick list for all states; worker scan must
            # only be blocked when the upstream order is cancelled.
            # Use f-string instead of _() to avoid shadowing of the
            # gettext shortcut by local '_' loop variables elsewhere
            # in this method scope.
            if so.status == 'cancelled':
                _name = so.display_order_name or so.name
                return {'type': 'so_invalid',
                        'error': f'⚠️ Order {_name} ถูก CANCELLED — ห้ามแพ็ค'}
            # Move from pending → picking + assign worker (delegated to
            # scan_pick when first SKU is shot, but flip status now so the
            # row decoration in the queue updates immediately).
            if so.status == 'pending':
                so.status = 'picking'
            if kob_worker_id and not so.kob_picker_id:
                so.kob_picker_id = kob_worker_id
            if not so.picker_id:
                so.picker_id = self.env.user
            return {'type': 'so_added',
                    'order_id': so.id,
                    'order_name': so.display_order_name or so.name}

        # 2) Treat as a product code — but first verify it IS a product so
        #    we can give a precise "Unknown barcode" error otherwise.
        product = self.env['product.product'].search([
            '|', ('default_code', '=', code), ('barcode', '=', code),
        ], limit=1)
        if not product:
            return {'type': 'error',
                    'error': _('Unknown barcode: %s') % code}

        if not active_order_ids:
            return {'type': 'error',
                    'error': _(
                        'No Active SO in basket — scan an order ref first.'
                    )}

        orders = self.browse(active_order_ids).exists().filtered(
            lambda o: o.status in ('pending', 'picking')
        ).sorted(key=lambda o: o.sale_order_date or o.create_date)

        if not orders:
            return {'type': 'error',
                    'error': _(
                        'All Active SOs already picked or shipped.'
                    )}

        # Auto-basket group: when 2+ SOs are picked together without a
        # pre-existing pick_group_id, create one on the fly. This makes the
        # multi-order gate (in scan_pick) engage so no SO advances to 'picked'
        # until ALL siblings are complete.
        if len(orders) > 1 and not all(o.pick_group_id for o in orders):
            existing = orders.mapped('pick_group_id')
            if existing:
                grp = existing[:1]
            else:
                lead = orders[0]
                grp = self.env['wms.pick.group'].sudo().create({
                    'name': f"AUTO-{lead.ref or lead.name}",
                    'source': 'auto_basket',
                    'state': 'picking',
                })
            unassigned = orders.filtered(lambda o: not o.pick_group_id)
            if unassigned:
                unassigned.write({'pick_group_id': grp.id})

        # Burst mode: 1 scan fills every basket line that still needs this
        # product. Worker หยิบของจากชั้นเป็น lot แล้วยิงครั้งเดียว — backend
        # loop scan_pick per unit so all existing rules apply (stock
        # reservation, picked_qty bounds, kob_worker assignment, activity
        # log, auto-status to 'picked' + pick_group gate).
        if burst:
            per_order = []
            total_filled = 0
            for order in orders:
                line = order._find_line_by_code(code)
                if not line:
                    continue
                need = max(0, int(line.expected_qty) - int(line.picked_qty))
                filled = 0
                for _ in range(need):
                    res = order.scan_pick(code, kob_worker_id=kob_worker_id)
                    if not res.get('ok'):
                        break
                    filled += 1
                if filled:
                    total_filled += filled
                    per_order.append({
                        'order_id': order.id,
                        'order_name': order.display_order_name or order.name,
                        'filled': filled,
                        'line_done': line.picked_qty >= line.expected_qty,
                        'all_picked_in_order': bool(order.all_picked),
                    })
            if total_filled == 0:
                return {'type': 'error',
                        'error': _(
                            'SKU %s not needed in any Active SO.'
                        ) % code}
            all_done = all(o.all_picked for o in orders)
            return {'type': 'burst',
                    'product_name': product.display_name,
                    'total_filled': total_filled,
                    'orders_touched': len(per_order),
                    'per_order': per_order,
                    'all_done_in_basket': bool(all_done)}

        for order in orders:
            line = order._find_line_by_code(code)
            if not line or line.picked_qty >= line.expected_qty:
                continue
            # Delegate to the single-order scan_pick — re-uses every existing
            # rule (delivery state, stock reservation, picked_qty++,
            # all_picked auto-status, _log_action, picker assignment).
            result = order.scan_pick(code, kob_worker_id=kob_worker_id)
            if not result.get('ok'):
                return {'type': 'error',
                        'error': result.get('error') or _('Pick failed')}
            all_done = all(o.all_picked for o in orders)
            bin_hint = order._kob_bin_hint()
            line_done = line.picked_qty >= line.expected_qty
            spoken_text = (
                f"ครบแล้ว {bin_hint['voice']}".strip()
                if line_done
                else f"ชิ้นที่ {line.picked_qty}"
            )
            return {'type': 'pick',
                    'order_id': order.id,
                    'order_name': order.display_order_name or order.name,
                    'line_id': line.id,
                    'product_name': line.product_id.display_name,
                    'all_picked_in_order': bool(order.all_picked),
                    'all_done_in_basket': bool(all_done),
                    'bin_hint': bin_hint,
                    'spoken_text': spoken_text}

        return {'type': 'error',
                'error': _(
                    'SKU %s not needed in any Active SO.'
                ) % code}

    def scan_pack(self, sku, kob_worker_id=None):
        """Pack one unit. Logs errors. Sets pack_start_at."""
        self.ensure_one()
        kob_wid = kob_worker_id or self._context.get('kob_worker_id')

        def _err(msg):
            self.pack_errors = (self.pack_errors or 0) + 1
            self._log_action('error_pack', sku or '', note=msg, kob_user_id=kob_wid)
            return {'ok': False, 'error': msg}

        # Cancelled guard — block packers same as scan_pick.
        if self.status == 'cancelled':
            when = fields.Datetime.to_string(self.cancelled_at) \
                if self.cancelled_at else _('unknown time')
            return _err(_(
                '⚠ ORDER CANCELLED at %s — do not pack. '
                'Move to Return queue.'
            ) % when)

        if self.status not in ('picked', 'packing'):
            return _err(_('Order must be picked first. Status: %s') % self.status)

        sku_norm = self._norm_code(sku)
        def _match(l):
            if l.packed_qty >= l.picked_qty:
                return False
            if l.sku and self._norm_code(l.sku) == sku_norm:
                return True
            if l.product_id:
                if l.product_id.default_code and self._norm_code(l.product_id.default_code) == sku_norm:
                    return True
                if l.product_id.barcode and self._norm_code(l.product_id.barcode) == sku_norm:
                    return True
            return False

        line = self.line_ids.filtered(_match)[:1]
        if not line:
            return _err(self._diagnose_scan_miss(sku))

        # Block pack scan if line has zero picked qty — picker hasn't taken
        # this product off the shelf yet, so packing it is invalid.
        if line.picked_qty <= 0:
            return _err(_(
                '🚫 ยังไม่ได้ pick — pack ไม่ได้\n'
                'SKU: %s\n'
                'ต้อง scan pick ก่อนถึงจะ pack ได้'
            ) % sku)

        if line.packed_qty >= line.picked_qty:
            return _err(_('Already fully packed: %s (%d/%d)') % (
                sku, line.packed_qty, line.picked_qty))

        line.packed_qty += 1
        # Auto-complete fee/service lines so they never block packing progress
        self._auto_complete_service_lines(phase='pack')
        now = fields.Datetime.now()
        if not self.packer_id:
            self.packer_id = self.env.user
        if not self.pack_start_at:
            self.pack_start_at = now
        previous_status = self.status
        self.status = 'packing'
        self._log_action('pack', sku, kob_user_id=kob_wid)
        if kob_wid and not self.kob_packer_id:
            self.kob_packer_id = kob_wid
        # Outgoing QC: create pending checks on first transition into packing
        if previous_status != 'packing':
            self.env['wms.quality.check'].sudo().register_for_order(self)
        bin_hint = self._kob_bin_hint()
        spoken = (f"ครบแล้ว {bin_hint['voice']}".strip()
                  if self.all_packed else f"แพ็คชิ้นที่ {line.packed_qty}")
        return {'ok': True,
                'all_packed': self.all_packed,
                'bin_hint': bin_hint,
                'spoken_text': spoken}

    def close_box(self, box_barcode=False, box_size=False, kob_worker_id=None):
        """Select box size → validate picking (cut stock) → auto invoice → print AWB."""
        self.ensure_one()
        if not self.all_packed:
            return {'ok': False, 'error': _('Not all items are packed yet.')}
        # Outgoing QC gate — block if any pending or failed checks
        pending = self.quality_check_ids.filtered(lambda q: q.state == 'pending')
        if pending:
            return {'ok': False, 'error': _(
                '🎯 Outgoing QC required — %d pending checks on: %s'
            ) % (len(pending),
                 ', '.join(pending.mapped('product_id.default_code')[:5]))}
        failed = self.quality_check_ids.filtered(lambda q: q.state == 'failed')
        if failed:
            return {'ok': False, 'error': _(
                '❌ Pack blocked — %d failed QC checks. Resolve defects first.'
            ) % len(failed)}

        # 0. Count lock — block BEFORE setting any status or posting invoice
        lock_msg = self._count_lock_msg()
        if lock_msg:
            return {'ok': False, 'error': lock_msg}

        if box_size:
            self.box_barcode = box_size
        elif box_barcode:
            self.box_barcode = box_barcode

        self._log_action('box', self.box_barcode or '', kob_user_id=kob_worker_id)

        # 1. Validate stock.picking → ตัด stock จริง
        stock_errors = self._validate_picking()

        if stock_errors:
            # Stock failed — do NOT set packed status, do NOT post invoice
            # Return ok: False so pack screen shows the error clearly
            return {'ok': False, 'error': stock_errors[0]}

        # 2. Stock OK → mark packed + auto invoice
        self.status = 'packed'
        self.packed_at = fields.Datetime.now()
        self._auto_create_invoice()

        # 3. Return AWB print action
        awb_action = None
        if self.awb:
            awb_action = {
                'report': 'kob_wms.report_wms_awb_label',
                'id': self.id,
            }

        return {
            'ok': True,
            'awb_action': awb_action,
        }

    def select_box_and_close(self, box_size, kob_worker_id=None):
        """Called from Pack screen: select box → close → returns print AWB info."""
        self.ensure_one()
        if not self.all_packed:
            return {'ok': False, 'error': _('Not all items are packed yet.')}
        return self.close_box(box_size=box_size, kob_worker_id=kob_worker_id)

    def _validate_picking(self):
        """Set move_line done qty = reserved qty, then validate delivery.

        Auto-retry strategy (no manual button needed):
          Attempt 1 — confirm + assign + set done=reserved + button_validate
          Attempt 2 — if state != done: unreserve → re-assign → set done=reserved
                      → button_validate again (handles stale reservation after
                        count-adjustment or external stock change)
          Failure   — clear error pointing supervisor to Inventory directly.

        Odoo 18 field names on stock.move.line:
          ml.quantity_product_uom = reserved qty
          ml.quantity             = done qty (set before button_validate)
          ml.picked               = True signals line ready to validate
        """
        errors = []
        for order in self:
            picking = order.picking_id

            # ── No picking ───────────────────────────────────────────────
            if not picking:
                msg = _('No delivery order linked — stock was NOT deducted. '
                        'Assign a Delivery Order and validate manually in Inventory.')
                errors.append(msg)
                order.message_post(body='⚠️ %s' % msg)
                continue

            # ── Already done ─────────────────────────────────────────────
            if picking.state == 'done':
                continue

            # ── Cancelled ────────────────────────────────────────────────
            if picking.state == 'cancel':
                msg = _('Delivery %s is cancelled — stock was NOT deducted.') % picking.name
                errors.append(msg)
                order.message_post(body='⚠️ %s' % msg)
                continue

            try:
                # ── Ensure picking is confirmed + reserved ────────────────
                if picking.state == 'draft':
                    picking.action_confirm()
                if picking.state in ('confirmed', 'waiting'):
                    picking.action_assign()

                # ── Attempt 1 ────────────────────────────────────────────
                ok = order._picking_attempt(picking)

                # ── Attempt 2: unreserve → re-assign → retry ─────────────
                if not ok:
                    picking.invalidate_recordset()   # flush ORM cache first
                    if picking.state == 'done':
                        ok = True
                    else:
                        picking.do_unreserve()
                        picking.action_assign()
                        ok = order._picking_attempt(picking)

                if ok:
                    order.message_post(body='✅ Stock validated: %s' % picking.name)
                else:
                    picking.invalidate_recordset()
                    msg = _(
                        '❌ Validation incomplete — delivery %s is still "%s".\n'
                        'กรุณาไปที่ Inventory → Transfers → %s แล้วกด Validate โดยตรง'
                    ) % (picking.name, picking.state, picking.name)
                    errors.append(msg)
                    order.message_post(body='⚠️ %s' % msg)

            except Exception as exc:
                msg = str(exc)
                errors.append(msg)
                order.message_post(body=_(
                    '❌ Stock validation error: %s\n'
                    'กรุณาไปที่ Inventory → Transfers → %s แล้ว Validate โดยตรง'
                ) % (msg, picking.name))

        return errors

    def _picking_attempt(self, picking):
        """Single validation attempt: set done=reserved → button_validate.

        Returns True if picking.state == 'done' after the attempt.
        Called by _validate_picking(); safe to call twice (idempotent).
        """
        # Guard: if all reserved qty = 0 after assign, stock is truly gone
        total_reserved = sum(ml.quantity_product_uom for ml in picking.move_line_ids)
        if total_reserved == 0 and picking.move_line_ids:
            return False   # will trigger attempt 2 (unreserve → re-assign)

        # Set done qty = reserved qty
        # Use quantity_product_uom (reserved per line) NOT move demand
        # to avoid over-counting when a move has multiple lot lines.
        for ml in picking.move_line_ids:
            reserved = ml.quantity_product_uom or 0
            if reserved > 0:
                ml.quantity = reserved
            if hasattr(ml, 'picked'):
                ml.picked = True

        # skip_immediate → bypass "Set Quantities" wizard
        # skip_backorder → bypass "Create Backorder?" wizard
        picking.with_context(
            skip_immediate=True,
            skip_backorder=True,
            picking_ids_not_to_backorder=picking.ids,
        ).button_validate()

        picking.invalidate_recordset()
        return picking.state == 'done'

    def _auto_create_invoice(self):
        """Auto create and post invoice from the linked sale.order."""
        for order in self:
            so = order.sale_order_id
            if not so:
                continue
            # Skip if invoice already exists
            if so.invoice_ids.filtered(lambda i: i.state != 'cancel'):
                continue
            try:
                # Create invoice from SO (uses delivery qty if policy=delivery)
                invoice = so._create_invoices()
                if invoice:
                    # Auto post (confirm) the invoice
                    invoice.action_post()
                    order.message_post(
                        body=_('Invoice created and posted: %s') % invoice.name)
            except Exception as exc:
                order.message_post(
                    body=_('Auto-invoice warning: %s') % exc)

    def action_fix_packed_status(self):
        """Supervisor: fix WMS orders where picking is 'done' but status not updated.

        Scenario B only — picking already validated externally (e.g. via Inventory UI),
        WMS status still shows wrong state. Auto-retry validation is built into
        _validate_picking() so this button covers only the manual-fix edge case.
        """
        fixed, skipped = [], []
        for order in self:
            picking = order.picking_id
            if picking and picking.state == 'done':
                if order.status not in ('packed', 'shipped', 'cancelled'):
                    order.status = 'packed'
                    if not order.packed_at:
                        order.packed_at = fields.Datetime.now()
                    # Create invoice if missing
                    so = order.sale_order_id
                    if so and not so.invoice_ids.filtered(lambda i: i.state == 'posted'):
                        order._auto_create_invoice()
                    order.message_post(body='✅ Status synced: picking was already done.')
                    fixed.append(order.name)
                else:
                    skipped.append(order.name)
            else:
                skipped.append(order.name)

        msg = []
        if fixed:   msg.append('✅ Fixed: %s' % ', '.join(fixed))
        if skipped: msg.append('⏭ Skipped (not applicable): %s' % ', '.join(skipped))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fix Packed Status'),
                'message': '\n'.join(msg) or 'Nothing to fix.',
                'type': 'success',
                'sticky': False,
            },
        }

    def action_skip_pack(self):
        """Skip the Pack stage entirely (pick → packed) and validate the
        underlying delivery, so the picking is closed and stock is moved
        the same way as a normal pack/close-box operation.

        Useful when the physical pack/scan station is unavailable but
        items are already picked and ready to ship — removes the manual
        scan-each-SKU step and any box selection.
        """
        for order in self:
            if order.status not in ('picked', 'packing'):
                raise UserError(_(
                    "Cannot skip Pack: order %s is in status '%s' "
                    "(need 'picked' or 'packing')."
                ) % (order.ref or order.name, order.status))
            if not order.all_picked:
                raise UserError(_(
                    "Cannot skip Pack: order %s has unpicked items "
                    "(%d / %d picked). Finish picking first."
                ) % (
                    order.ref or order.name,
                    order.picked_total or 0,
                    order.expected_total or 0,
                ))

            # Mirror picked_qty into packed_qty so reports stay consistent
            for line in order.line_ids:
                if (line.packed_qty or 0) < (line.picked_qty or 0):
                    line.packed_qty = line.picked_qty

            # Validate underlying picking (move stock + create backorder if any)
            if order.picking_id:
                try:
                    order._validate_picking()
                except Exception as e:
                    _logger.exception(
                        "skip_pack: _validate_picking failed for %s",
                        order.name,
                    )
                    raise UserError(_(
                        "Skip Pack failed: stock validation error — %s"
                    ) % str(e)[:300])

            order.status = 'packed'
            order.packed_at = fields.Datetime.now()
            order._log_action('skip_pack', order.ref or order.name,
                              note='Pack stage skipped — pack tool unavailable')
        return True

    def action_skip_pack_and_ship(self):
        """One-shot: skip pack → ship immediately. For picked orders that
        should go straight out the door without a separate ship action.
        """
        self.action_skip_pack()
        return self.action_ship()

    def action_ship(self):
        """Mark as shipped + create scan item + auto add to active batch.

        Skip-Pack mode (toggle via res.company.wms_skip_pack):
            When the scan/pack station is unavailable, OUT consolidates
            Pack's responsibilities. If status=='picked', this method
            auto-runs:
                * _validate_picking()    → cut stock
                * _auto_create_invoice() → post invoice
                * status = 'packed'      → packed_at stamped
            then proceeds to ship as usual. Toggle off the flag when the
            pack tool is ready and the normal Pick → Pack → Out flow
            resumes.
        """
        for order in self:
            company = order.company_id or self.env.company

            # ── Skip-Pack mode: do Pack's work inline before shipping ──
            if order.status == 'picked' and getattr(
                company, 'wms_skip_pack', False
            ):
                if not order.all_picked:
                    return {'ok': False, 'error': _(
                        "Cannot ship — order %s has unpicked items."
                    ) % order.name}
                # Mirror picked_qty into packed_qty for accurate reports
                for line in order.line_ids:
                    if (line.packed_qty or 0) < (line.picked_qty or 0):
                        line.packed_qty = line.picked_qty

                # Auto-assign a default box (no manual selection) so reports
                # have a box reference. Prefer suggested_box_id (volume-based);
                # fallback to smallest active box; final fallback: leave blank.
                if not order.actual_box_id:
                    default_box = order.suggested_box_id
                    if not default_box:
                        default_box = self.env['wms.box.size'].search([
                            ('active', '=', True),
                        ], order='volume_cm3 asc', limit=1)
                    if default_box:
                        order.box_barcode = default_box.code

                if order.picking_id:
                    stock_errors = order._validate_picking()
                    if stock_errors:
                        return {'ok': False, 'error': stock_errors[0]}
                try:
                    order._auto_create_invoice()
                except Exception as e:
                    _logger.exception(
                        "skip_pack ship: _auto_create_invoice failed for %s",
                        order.name,
                    )
                    # Don't block ship if invoice fails — just log
                order.status = 'packed'
                order.packed_at = fields.Datetime.now()
                order._log_action('skip_pack', order.ref or order.name,
                                  note='Pack stage skipped — invoice + stock '
                                       '+ auto-box handled at OUT')

            if order.status != 'packed':
                return {'ok': False, 'error': _('Order %s is not packed.') % order.name}

            order.status = 'shipped'
            order.shipped_at = fields.Datetime.now()
            order.shipper_id = self.env.user
            order._log_action('ship', order.awb or '')

            # Create scan item — only when courier is assigned
            # (courier_id is required on wms.scan.item).
            # Auto-mark as scanned (scanned_qty = expected_qty) so the
            # dispatch screen does NOT require redundant per-AWB rescan;
            # pack-stage barcode verification already established the link
            # and the audit trail (sales_order_id, AWB, courier, batch_id)
            # is preserved on the scan item itself.
            scan_item = None
            if order.awb and order.courier_id:
                scan_item = self.env['wms.scan.item'].create({
                    'barcode': order.awb,
                    'courier_id': order.courier_id.id,
                    'order_ref': order.ref or order.name,
                    'shop_name': order.platform or '',
                    'sales_order_id': order.id,
                    'expected_qty': 1,
                    'scanned_qty': 1,
                })

            # Auto-add to active scanning batch (or create one) — round-aware.
            # One batch per (courier_id, dispatch_round_date, dispatch_round_number).
            # SOs shipped before company.wms_dispatch_cutoff_time land in today's
            # round; after cut-off they roll into the next day's round.
            if scan_item:
                Batch = self.env['wms.courier.batch']
                round_date, round_no = Batch._compute_round_date()
                batch = Batch.search([
                    ('courier_id', '=', order.courier_id.id),
                    ('dispatch_round_date', '=', round_date),
                    ('dispatch_round_number', '=', round_no),
                    ('state', 'in', ['draft', 'scanning']),
                ], limit=1)
                if not batch:
                    batch = Batch.create({
                        'state': 'scanning',
                        'courier_id': order.courier_id.id,
                        'dispatch_round_date': round_date,
                        'dispatch_round_number': round_no,
                        'work_date': round_date,
                    })
                scan_item.batch_id = batch.id

                # Tag the underlying sale.order with a crm.tag matching the
                # batch name so operations can filter "all SOs of
                # ROUND-1/SHOPEE/2026-05-15" from the standard SO list view.
                if order.sale_order_id:
                    Tag = self.env['crm.tag'].sudo()
                    tag = Tag.search([('name', '=', batch.name)], limit=1)
                    if not tag:
                        tag = Tag.create({'name': batch.name})
                    order.sale_order_id.sudo().write({
                        'tag_ids': [(4, tag.id)],
                    })

        # Navigate back to Outbound Queue after shipping
        action = self.env.ref('kob_wms.action_wms_outbound_screen').sudo().read()[0]
        action['target'] = 'main'
        return action

    def set_awb_and_ship(self, awb):
        """Set AWB barcode then ship. Called from Outbound screen.

        Returns a dict the OWL screen can consume directly (ok, bin_hint,
        spoken_text). Skips the navigation action that `action_ship`
        returns — the screen handles its own re-render via loadOrders.
        """
        self.ensure_one()
        if self.status != 'packed':
            return {
                'ok': False,
                'error': _('Order %s is not packed.') % self.name,
            }
        self.awb = awb
        # Capture the bin hint BEFORE action_ship() flips status to
        # 'shipped' (so courier metadata is still available even if
        # action_ship reassigns batch / clears courier).
        bin_hint = self._kob_bin_hint()
        spoken = f"จ่ายออก {bin_hint['voice']}".strip()
        try:
            self.action_ship()
        except Exception as e:
            return {'ok': False, 'error': str(e)}
        return {
            'ok': True,
            'bin_hint': bin_hint,
            'spoken_text': spoken,
            'awb': awb,
            'order_name': self.display_order_name or self.name,
        }

    # ------------------------------------------------------------------
    # Auto-Box Sizing
    # ------------------------------------------------------------------
    def get_recommended_box(self):
        """Recommend the smallest box that fits all order items.

        Algorithm:
        1.  Sum product.volume * picked_qty for every line.
            (product.volume is stored in m³ in Odoo.)
        2.  Apply 25 % packing buffer.
        3.  Find the smallest wms.box.size with volume (m³) >= required.
        4.  If no product volumes are set, fall back to item-count heuristic.
        """
        self.ensure_one()

        lines = self.env['wms.sales.order.line'].search([('order_id', '=', self.id)])
        total_volume_m3 = 0.0
        total_weight_kg = 0.0
        has_dims = False

        for line in lines:
            qty = line.picked_qty or 1
            if line.product_id:
                if line.product_id.volume:
                    total_volume_m3 += line.product_id.volume * qty
                    has_dims = True
                if line.product_id.weight:
                    total_weight_kg += line.product_id.weight * qty

        BoxSize = self.env['wms.box.size']

        # ── No dimensions available → heuristic by item count ──────────
        if not has_dims or total_volume_m3 <= 0:
            n_items = sum(l.picked_qty or 1 for l in lines)
            if n_items <= 2:
                code_fallback = 'B'
            elif n_items <= 5:
                code_fallback = 'C'
            elif n_items <= 10:
                code_fallback = '2C'
            else:
                code_fallback = 'L'
            box = BoxSize.search([('code', '=', code_fallback), ('active', '=', True)], limit=1) \
                or BoxSize.search([('active', '=', True)], order='volume asc', limit=1)
            if box:
                self.sudo().write({'suggested_box_id': box.id})
                return {
                    'ok': True,
                    'box_code': box.code,
                    'box_label': box.name_get()[0][1],
                    'box_volume_cm3': box.volume_cm3,
                    'total_volume_cm3': 0,
                    'basis': 'item_count',
                    'note': _('No product dimensions set — estimated from item count (%d items)') % n_items,
                }
            return {'ok': False, 'error': _('No box sizes configured. Please add box sizes in WMS settings.')}

        # ── Volume-based recommendation ────────────────────────────────
        required_m3 = total_volume_m3 * 1.25  # 25 % packing buffer

        box = BoxSize.search(
            [('active', '=', True), ('volume', '>=', required_m3)],
            order='volume asc',
            limit=1,
        )
        if not box:
            # Everything is too big — return the largest box
            box = BoxSize.search([('active', '=', True)], order='volume desc', limit=1)

        if not box:
            return {'ok': False, 'error': _('No box sizes configured.')}

        # Weight warning (informational)
        weight_note = ''
        if box.weight_limit and total_weight_kg > box.weight_limit:
            weight_note = _(' ⚠ Weight %.1f kg exceeds box limit %.1f kg') % (
                total_weight_kg, box.weight_limit)

        self.sudo().write({'suggested_box_id': box.id})
        return {
            'ok': True,
            'box_code':        box.code,
            'box_label':       box.name_get()[0][1],
            'box_volume_cm3':  box.volume_cm3,
            'total_volume_cm3': round(total_volume_m3 * 1_000_000, 2),
            'required_volume_cm3': round(required_m3 * 1_000_000, 2),
            'total_weight_kg': round(total_weight_kg, 3),
            'basis': 'volume',
            'note': weight_note,
        }

    @api.model
    def action_return_scan(self, code, kob_worker_id=None):
        """Return-mode scan from the mobile Return screen.

        Resolves ``code`` against the same identifier fields used elsewhere
        in the WMS (name / so_name / ref / awb / display_order_name /
        box_barcode), tolerating Excel float artifacts via ``_norm_code``.

        Outcomes:
        - match found + status='cancelled' + not yet returned →
          stamp ``returned_at`` + ``returned_by_id``, log to activity log,
          return ``{ok: True, original_order_date: ..., name: ...}``
        - match found but status ≠ 'cancelled' → return ``{ok: False,
          error: 'not cancelled — no return'}``
        - match found but already returned → return ``{ok: False,
          error: 'already returned at ...'}``
        - no match → return ``{ok: False, error: 'not found'}``

        ``code`` is searched across ALL companies the calling user can see
        (ir.rule still applies); the worker's company switcher should be
        on for both KOB and BTV when they handle multi-company returns.
        """
        if not code or not str(code).strip():
            return {'ok': False, 'error': _('Empty scan')}

        norm = self._norm_code(code)

        match_fields = (
            'name', 'so_name', 'ref', 'awb',
            'display_order_name', 'box_barcode',
        )
        domain = []
        for idx, fname in enumerate(match_fields):
            domain.append('|' if idx < len(match_fields) - 1 else None)
        # Build an OR-chain domain across the identifier fields, normalised
        # against the trailing-dot Excel artifact by checking both raw +
        # normalised values.
        candidates = self.search([])  # ir.rule already restricts visibility

        def _key(rec):
            for f in match_fields:
                val = getattr(rec, f, None)
                if val and self._norm_code(val) == norm:
                    return True
            return False

        rec = candidates.filtered(_key)[:1]
        if not rec:
            return {'ok': False, 'error': _(
                '⚠ ไม่พบ order "%s" — ตรวจ AWB/Ref อีกครั้ง'
            ) % code}

        if rec.status != 'cancelled':
            return {'ok': False, 'error': _(
                '⚠ %s (status: %s) — ไม่ได้ cancelled ห้ามรับคืน'
            ) % (rec.name, rec.status)}

        if rec.returned_at:
            return {'ok': False, 'error': _(
                '⚠ %s รับคืนไปแล้วเมื่อ %s'
            ) % (rec.name, fields.Datetime.to_string(rec.returned_at))}

        rec.sudo().write({
            'returned_at': fields.Datetime.now(),
            'returned_by_id': kob_worker_id or False,
        })
        try:
            rec._log_action(
                'return', code,
                note=_('Returned via mobile Return scan'),
                kob_user_id=kob_worker_id,
            )
        except Exception:  # noqa: BLE001
            pass

        original_date = False
        if rec.sale_order_id and rec.sale_order_id.date_order:
            original_date = fields.Date.to_string(
                fields.Datetime.to_datetime(rec.sale_order_id.date_order).date()
            )

        return {
            'ok': True,
            'id': rec.id,
            'name': rec.name,
            'original_order_date': original_date,
        }

    def action_cancel(self):
        """Cancel one or more WMS orders.

        Stamps the audit fields (cancelled_at + cancelled_by_id) and writes
        an entry to wms.activity.log so the Cancel Report can render the
        timeline. Idempotent — re-cancelling an already-cancelled row is a
        no-op and does not overwrite the original cancellation timestamp.
        """
        for rec in self:
            if rec.status == 'cancelled':
                continue
            rec.write({
                'status': 'cancelled',
                'cancelled_at': fields.Datetime.now(),
                'cancelled_by_id': self.env.uid,
            })
            try:
                rec._log_action(
                    'cancel', '',
                    note=_('Cancelled via action_cancel'),
                )
            except Exception:  # noqa: BLE001
                # Never let logging break the cancel itself.
                pass

    def action_force_picked(self):
        """Manager override: mark this SO as picked despite incomplete group.

        Bypasses the multi-order group gate. Logs an audit message. Use only
        for exception handling (group split, customer cancellation, missing
        stock written off, etc.). Member SOs with all_picked=True but stuck
        in 'picking' due to siblings → unblock them individually here.
        """
        if not self.env.user.has_group('kob_wms.group_wms_manager'):
            raise UserError(
                "Only WMS Manager can force-promote an order to Picked.")
        now = fields.Datetime.now()
        for so in self:
            if so.status not in ('picking', 'pending'):
                continue
            if not so.all_picked:
                raise UserError(
                    f"{so.display_name}: cannot force Picked — "
                    f"{so.picked_total}/{so.expected_total} items only. "
                    f"Use Cancel/Return wizard for partial situations.")
            so.write({'status': 'picked', 'picked_at': now})
            so.message_post(
                body=(f"Status forced to <b>Picked</b> by "
                      f"{self.env.user.display_name} "
                      f"(group gate override).")
            )
        return True

    def action_open_cancel_return(self):
        """Open Cancel / Return wizard for this order."""
        self.ensure_one()
        wizard = self.env['wms.cancel.return.wizard'].create({'order_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wms.cancel.return.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_list_ship(self, scanned_val=None):
        """Ship from outbound list scan bar. Returns JSON dict (not an act_window).

        scanned_val — the raw barcode the worker scanned.  If the order has no
        AWB yet and scanned_val looks like a courier tracking number (not a WMS
        order name), it is saved as the AWB before shipping.
        """
        self.ensure_one()
        if self.status != 'packed':
            return {
                'ok': False,
                'error': _('Not packed yet (status: %s)') % self.status,
            }
        # Auto-fill AWB from the scanned barcode when it is not yet set.
        # Skip obvious non-AWB values (WMS order names start with "SO/").
        if scanned_val and not self.awb:
            if not scanned_val.upper().startswith('SO/'):
                self.awb = scanned_val

        result = self.action_ship()
        # action_ship returns {ok: False, error: ...} on error, else an act_window dict
        if isinstance(result, dict) and result.get('ok') is False:
            return result
        return {'ok': True, 'name': self.name, 'awb': self.awb or ''}

    # ------------------------------------------------------------------
    # Scan wizard launchers (form buttons)
    # ------------------------------------------------------------------
    def _open_scan_wizard(self, mode):
        self.ensure_one()
        return self.env['wms.scan.wizard'].action_open_from_order(self.id, mode)

    def action_open_scan_pick(self):
        return self._open_scan_wizard('pick')

    def action_open_scan_pack(self):
        return self._open_scan_wizard('pack')

    def action_open_scan_box(self):
        return self._open_scan_wizard('box')

    def action_scan_item(self, barcode, kob_worker_id=None):
        """Direct scan from the form view scan bar.
        Routes to scan_pick or scan_pack based on current status.
        Returns a JSON-friendly dict: {ok, msg, all_done, new_status} or {ok, error}.
        """
        self.ensure_one()
        barcode = (barcode or '').strip()
        if not barcode:
            return {'ok': False, 'error': _('Empty barcode')}

        # Cancelled guard — same surface as scan_pick / scan_pack.
        if self.status == 'cancelled':
            when = fields.Datetime.to_string(self.cancelled_at) \
                if self.cancelled_at else _('unknown time')
            return {'ok': False, 'error': _(
                '⚠ ORDER CANCELLED at %s — do not scan. '
                'Move to Return queue.'
            ) % when}

        status_before = self.status
        if status_before in ('pending', 'picking'):
            ctx = dict(self._context, kob_worker_id=kob_worker_id) if kob_worker_id else self._context
            result = self.with_context(ctx).scan_pick(barcode)
        elif status_before in ('picked', 'packing'):
            result = self.scan_pack(barcode, kob_worker_id=kob_worker_id)
        else:
            return {'ok': False, 'error': _('Cannot scan in status: %s') % self.status}

        if not result.get('ok'):
            return result  # already has 'error' key from scan_pick/scan_pack

        # Build a progress message from the matched line (quantities are now updated)
        b_up = barcode.upper()
        line = self.line_ids.filtered(
            lambda l: (l.sku or '').upper() == b_up
            or (l.product_id.barcode or '') == barcode
            or (l.product_id.default_code or '').upper() == b_up
        )[:1]

        if status_before in ('pending', 'picking'):
            msg = (_('%s: %d/%d picked') % (line.sku, int(line.picked_qty), int(line.expected_qty))
                   if line else _('Picked'))
            all_done = self.all_picked
            phase = 'pick'
        else:
            msg = (_('%s: %d/%d packed') % (line.sku, int(line.packed_qty), int(line.picked_qty))
                   if line else _('Packed'))
            all_done = self.all_packed
            phase = 'pack'

        return {
            'ok': True,
            'msg': msg,
            'all_done': bool(all_done),
            'phase': phase,           # 'pick' | 'pack'
            'new_status': self.status,
        }

    def action_get_close_box_data(self):
        """Return box suggestion + all available boxes for the close box dialog."""
        self.ensure_one()
        suggestion = self.get_recommended_box()
        boxes = self.env['wms.box.size'].search([('active', '=', True)], order='volume asc')
        return {
            'ok': True,
            'suggestion': suggestion,
            'boxes': [{'code': b.code, 'label': b.display_name} for b in boxes],
            'order_name': self.name,
        }

    def action_import_from_sale_order(self):
        """Create lines from the linked sale.order (or stock.picking)."""
        self.ensure_one()
        if not (self.sale_order_id or self.picking_id):
            raise UserError(_('Link a Sale Order or Delivery Order first.'))
        self.line_ids.unlink()
        lines = []
        source_picking = self.picking_id
        if self.sale_order_id:
            if not self.ref:
                self.ref = self.sale_order_id.name
            if not self.partner_id:
                self.partner_id = self.sale_order_id.partner_id
                self.customer = self.sale_order_id.partner_id.name
            for sol in self.sale_order_id.order_line:
                if not (sol.product_id and sol.product_uom_qty > 0):
                    continue
                # Skip service / non-storable products (e.g. Logistics Fees,
                # Platform Fees). These appear on the SO + invoice but are
                # not physical items the warehouse picks/packs/scans, so
                # they would never reach picked_qty and would block the
                # auto-done transition.
                prod = sol.product_id
                if prod.type == "service":
                    continue
                if "is_storable" in prod._fields and not prod.is_storable:
                    continue
                lines.append({
                    'order_id': self.id,
                    'product_id': prod.id,
                    'product_name': prod.display_name,
                    'sku': prod.default_code or prod.barcode or '',
                    'expected_qty': int(sol.product_uom_qty),
                })
            if not source_picking:
                source_picking = self.sale_order_id.picking_ids[:1]
                if source_picking:
                    self.picking_id = source_picking
        elif source_picking:
            if not self.ref:
                self.ref = source_picking.name
            if not self.partner_id:
                self.partner_id = source_picking.partner_id
                self.customer = source_picking.partner_id.name
            for ml in source_picking.move_ids:
                if not (ml.product_id and ml.product_uom_qty > 0):
                    continue
                prod = ml.product_id
                # Skip service / non-storable products.
                if prod.type == "service":
                    continue
                if "is_storable" in prod._fields and not prod.is_storable:
                    continue
                lines.append({
                    'order_id': self.id,
                    'product_id': prod.id,
                    'product_name': prod.display_name,
                    'sku': prod.default_code or prod.barcode or '',
                    'expected_qty': int(ml.product_uom_qty),
                })
        if lines:
            self.env['wms.sales.order.line'].create(lines)
        return True

    def _log_action(self, action, code='', note='', kob_user_id=None):
        self.env['wms.activity.log'].create({
            'user_id': self.env.user.id,
            'kob_user_id': kob_user_id or False,
            'action': action,
            'ref': self.ref or self.name,
            'code': code,
            'sales_order_id': self.id,
            'note': note,
        })

    # ------------------------------------------------------------------
    # Demo KPI seed — assign WMS workers to existing orders
    # ------------------------------------------------------------------
    @api.model
    def action_seed_demo_workers(self):
        """
        Spread kob.wms.user workers across existing orders and fill in
        missing timestamps so KPI / SLA views show realistic sample data.
        Call from: All Orders list → Actions → Seed Demo Workers.
        """
        import random
        from datetime import datetime, timedelta

        KobUser = self.env['kob.wms.user'].sudo()
        pickers = KobUser.search([
            ('role', 'in', ['picker', 'admin', 'supervisor']),
            ('is_active', '=', True),
        ])
        packers = KobUser.search([
            ('role', 'in', ['packer', 'admin', 'supervisor']),
            ('is_active', '=', True),
        ])

        if not pickers:
            pickers = KobUser.search([('is_active', '=', True)])
        if not packers:
            packers = pickers

        orders = self.sudo().search(
            [('status', 'not in', ['cancelled'])],
            order='id asc',
        )

        now = fields.Datetime.now()
        updated = 0

        for idx, order in enumerate(orders):
            picker = pickers[idx % len(pickers)]
            packer = packers[idx % len(packers)]

            # Random base time: 0–14 days ago, between 08:00–11:00
            days_ago = random.randint(0, 14)
            hour_offset = random.randint(0, 180)  # minutes after 08:00
            base = (now - timedelta(days=days_ago)).replace(
                hour=8, minute=0, second=0, microsecond=0
            ) + timedelta(minutes=hour_offset)

            vals = {
                'kob_picker_id': picker.id,
                'kob_packer_id': packer.id,
            }

            status = order.status
            # SLA start (picklist printed)
            if not order.sla_start_at and status != 'pending':
                vals['sla_start_at'] = base

            sla_base = order.sla_start_at or base

            if status in ('picking', 'picked', 'packing', 'packed', 'shipped'):
                if not order.pick_start_at:
                    vals['pick_start_at'] = sla_base + timedelta(
                        minutes=random.randint(3, 15))

            pick_start = order.pick_start_at or vals.get('pick_start_at', sla_base)

            if status in ('picked', 'packing', 'packed', 'shipped'):
                if not order.picked_at:
                    vals['picked_at'] = pick_start + timedelta(
                        minutes=random.randint(20, 55))

            picked_at = order.picked_at or vals.get('picked_at', pick_start + timedelta(minutes=30))

            if status in ('packing', 'packed', 'shipped'):
                if not order.pack_start_at:
                    vals['pack_start_at'] = picked_at + timedelta(
                        minutes=random.randint(1, 8))

            pack_start = order.pack_start_at or vals.get('pack_start_at', picked_at + timedelta(minutes=3))

            if status in ('packed', 'shipped'):
                if not order.packed_at:
                    vals['packed_at'] = pack_start + timedelta(
                        minutes=random.randint(8, 25))

            packed_at = order.packed_at or vals.get('packed_at', pack_start + timedelta(minutes=15))

            if status == 'shipped':
                if not order.shipped_at:
                    vals['shipped_at'] = packed_at + timedelta(
                        minutes=random.randint(5, 30))

            order.sudo().write(vals)
            updated += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Assigned demo workers to %d orders. Refresh KPI view.' % updated,
                'type': 'success',
                'sticky': False,
            },
        }

    # ───────────────────────────────────────────────────────────────────
    # Audit Hash — Blockchain-style tamper detection with Boat recovery
    # ───────────────────────────────────────────────────────────────────
    _AUDIT_TERMINAL_STATES = ('packed', 'shipped', 'cancelled')

    def _build_audit_snapshot(self) -> dict:
        """Deterministic dict for SHA-256. Sorted keys via json.dumps."""
        self.ensure_one()
        lines = []
        for ln in self.line_ids.sorted(lambda l: l.id):
            lines.append({
                'id': ln.id,
                'product_id': ln.product_id.id or False,
                'sku': ln.sku or '',
                'expected_qty': float(ln.expected_qty or 0.0),
                'picked_qty': float(ln.picked_qty or 0.0),
                'packed_qty': float(ln.packed_qty or 0.0),
            })
        return {
            'name': self.name or '',
            'ref': self.ref or '',
            'platform': self.platform or '',
            'status': self.status or '',
            'partner_id': self.partner_id.id or False,
            'courier_id': self.courier_id.id or False,
            'awb': self.awb or '',
            'box_barcode': self.box_barcode or '',
            'sale_order_id': self.sale_order_id.id or False,
            'lines': lines,
        }

    def _compute_audit_snapshot(self) -> str:
        """SHA-256 hex digest of canonical JSON snapshot."""
        import hashlib
        import json
        self.ensure_one()
        snap = self._build_audit_snapshot()
        raw = json.dumps(snap, sort_keys=True, default=str).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    def _seal_audit_hash(self, source: str = 'realtime') -> None:
        """Seal hash for this record. Idempotent if already sealed
        and snapshot unchanged."""
        self.ensure_one()
        new_hash = self._compute_audit_snapshot()
        if self.audit_hash == new_hash:
            return
        self.sudo().write({
            'audit_hash': new_hash,
            'audit_hash_at': fields.Datetime.now(),
            'audit_hash_user_id': self.env.uid,
            'audit_hash_source': source,
        })
        self.env['wms.activity.log'].sudo().create({
            'action': 'seal_audit',
            'ref': self.name,
            'code': new_hash[:16],
            'note': f'sealed at status={self.status} src={source}',
            'sales_order_id': self.id,
        })

    def write(self, vals):
        """Override to auto-seal on terminal status transition."""
        res = super().write(vals)
        if 'status' in vals and vals['status'] in self._AUDIT_TERMINAL_STATES:
            for order in self:
                if order.status in self._AUDIT_TERMINAL_STATES \
                        and not order.audit_hash:
                    try:
                        order._seal_audit_hash(source='realtime')
                    except Exception as exc:  # noqa: BLE001
                        _logger.warning(
                            'audit seal failed for %s: %s', order.name, exc)
        return res

    def _fetch_boat_snapshot(self) -> tuple[str, dict] | tuple[None, str]:
        """Fetch live data from Boat RDS for this order via psycopg2.

        Returns (hash, snapshot) on success, or (None, error_msg) on failure.
        Requires linked sale.order with x_boat_id field populated.
        """
        self.ensure_one()
        sale_order = self.sale_order_id
        if not sale_order:
            return None, 'no_linked_sale_order'
        boat_id = getattr(sale_order, 'x_boat_id', None)
        if not boat_id:
            return None, 'no_x_boat_id'
        try:
            import psycopg2
            import psycopg2.extras
            dsn = self.env['kob.boat.sync.dsn'].get_dsn()
        except Exception as exc:  # noqa: BLE001
            return None, f'boat_offline:{exc}'
        try:
            import hashlib
            import json
            with psycopg2.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor(
                    cursor_factory=psycopg2.extras.RealDictCursor
                ) as cur:
                    cur.execute(
                        'SELECT id, name, date_order, origin, note, state '
                        'FROM sale_order WHERE id = %s', (boat_id,))
                    header = cur.fetchone()
                    if not header:
                        return None, 'not_in_boat'
                    cur.execute(
                        'SELECT id, product_id, product_uom_qty, price_unit, '
                        'discount, name FROM sale_order_line '
                        'WHERE order_id = %s ORDER BY id ASC', (boat_id,))
                    lines = [dict(r) for r in cur.fetchall()]
            snap = {
                'boat_id': boat_id,
                'header': {k: str(v) if v is not None else '' for k, v
                           in header.items()},
                'lines': [{k: str(v) if v is not None else '' for k, v
                           in ln.items()} for ln in lines],
            }
            raw = json.dumps(snap, sort_keys=True).encode('utf-8')
            return hashlib.sha256(raw).hexdigest(), snap
        except Exception as exc:  # noqa: BLE001
            return None, f'boat_query_failed:{exc}'

    def get_audit_status(self) -> dict:
        """Return audit state for UI badge. Caller = controller."""
        self.ensure_one()
        sealed = self.audit_hash or ''
        if not sealed:
            return {
                'result': 'UNSEALED',
                'hash_short': '',
                'sealed_at': False,
                'message': 'Not yet sealed (terminal status not reached)',
            }
        current = self._compute_audit_snapshot()
        boat_hash, boat_info = self._fetch_boat_snapshot()
        result = 'VERIFIED'
        if sealed != current:
            result = 'TAMPERED'
        elif boat_hash is None:
            if boat_info in ('no_linked_sale_order', 'no_x_boat_id',
                             'not_in_boat'):
                result = 'NOT_IN_BOAT'
            else:
                result = 'BOAT_OFFLINE'
        elif boat_hash != sealed and boat_hash != current:
            result = 'DIVERGED'
        return {
            'result': result,
            'hash_short': sealed[:10] + '…',
            'sealed_at': fields.Datetime.to_string(self.audit_hash_at)
                if self.audit_hash_at else False,
            'message': boat_info if isinstance(boat_info, str)
                else 'ok',
        }

    def action_recover_from_boat(self) -> dict:
        """Re-sync this order's underlying sale.order from Boat, then re-seal.

        Triggers kob.boat.sync._pull_one() with a pinned where_clause so only
        this record's sale.order id is fetched. Manager/admin gated.
        """
        self.ensure_one()
        if not self.env.user.has_group('kob_wms.group_wms_manager'):
            raise UserError(_('Only managers can trigger Boat recovery.'))
        sale_order = self.sale_order_id
        if not sale_order or not getattr(sale_order, 'x_boat_id', None):
            raise UserError(_('No linked sale.order with x_boat_id.'))
        boat_id = sale_order.x_boat_id
        Target = self.env['kob.boat.sync.target']
        target = Target.sudo().search([
            ('odoo_model', '=', 'sale.order'),
        ], limit=1)
        if not target:
            raise UserError(_('No kob.boat.sync.target for sale.order.'))
        # Pin where_clause to this single boat id (in-memory only,
        # we use cursor savepoint to avoid persisting the change).
        sp = 'boat_recover_pin'
        self.env.cr.execute(f'SAVEPOINT "{sp}"')
        try:
            target.sudo().write({
                'where_clause': f'id = {int(boat_id)}',
                'cursor_id': 0,
            })
            old_hash = self.audit_hash or ''
            self.env['kob.boat.sync'].sudo()._pull_one(target)
            self.invalidate_recordset()
            new_hash = self._compute_audit_snapshot()
            self.sudo().write({
                'audit_hash': new_hash,
                'audit_hash_at': fields.Datetime.now(),
                'audit_hash_user_id': self.env.uid,
                'audit_hash_source': 'recovery',
            })
            self.env['wms.activity.log'].sudo().create({
                'action': 'auto_healed_from_boat',
                'ref': self.name,
                'code': new_hash[:16],
                'note': f'healed: {old_hash[:16]}… → {new_hash[:16]}…',
                'sales_order_id': self.id,
            })
        finally:
            self.env.cr.execute(f'ROLLBACK TO SAVEPOINT "{sp}"')
            self.env.cr.execute(f'RELEASE SAVEPOINT "{sp}"')
        return {'result': 'VERIFIED', 'hash_short': new_hash[:10] + '…'}


class WmsSalesOrderLine(models.Model):
    _name = 'wms.sales.order.line'
    _description = 'WMS Sales Order Line'
    _order = 'sequence, id'

    order_id = fields.Many2one('wms.sales.order', string='Order',
                               required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    sku = fields.Char(string='SKU / Barcode', required=True)
    product_name = fields.Char(string='Product Name')
    product_id = fields.Many2one('product.product', string='Product')
    expected_qty = fields.Integer(string='Expected', default=1)
    picked_qty = fields.Integer(string='Picked', default=0)
    packed_qty = fields.Integer(string='Packed', default=0)
    product_barcode = fields.Char(
        related='product_id.barcode', string='Barcode', readonly=True,
        help='EAN/UPC barcode from product master — this is what the scanner reads.',
    )
    # Referenced by the wms.sales.order.form embedded list (view id 3391):
    #   <field name="product_image_128" widget="image" ... />
    # Without this related declaration the form crashes with:
    #   "wms.sales.order.line"."product_image_128" field is undefined.
    product_image_128 = fields.Image(
        related='product_id.image_128', string='Image',
        readonly=True, store=False,
    )
    remaining_pick = fields.Integer(compute='_compute_remaining', store=False)
    remaining_pack = fields.Integer(compute='_compute_remaining', store=False)

    # True for service/fee lines that should NOT require scanning
    is_service = fields.Boolean(
        compute='_compute_is_service', store=True,
        string='Fee / Service Line',
        help='Auto-detected: service products or logistics/fee SKUs skip scanning.',
    )

    # Keywords in SKU or product name that identify a fee/service line
    _FEE_KEYWORDS = ('logistic', 'logistics', 'fee', 'fees', 'freight',
                     'shipping', 'delivery fee', 'rev-', 'service')

    @api.depends('product_id', 'product_id.type', 'sku', 'product_name')
    def _compute_is_service(self):
        for line in self:
            if line.product_id and line.product_id.type == 'service':
                line.is_service = True
            else:
                haystack = ' '.join(filter(None, [
                    (line.sku or '').lower(),
                    (line.product_name or '').lower(),
                ]))
                line.is_service = any(kw in haystack for kw in self._FEE_KEYWORDS)

    @api.depends('expected_qty', 'picked_qty', 'packed_qty')
    def _compute_remaining(self):
        for line in self:
            line.remaining_pick = max(line.expected_qty - line.picked_qty, 0)
            line.remaining_pack = max(line.picked_qty - line.packed_qty, 0)

    # Availability gate — surfaces "Available / Out of Stock" per line so
    # picker sees the red flag BEFORE attempting to scan.
    availability_state = fields.Selection(
        [('available', 'Available'),
         ('partial', 'Partial'),
         ('not_available', 'Not Available')],
        compute='_compute_availability_state',
        store=False,
    )
    available_qty = fields.Float(
        compute='_compute_availability_state', store=False,
        help='Reserved quantity on the linked delivery for THIS product. '
             '0 = stock vanished after picking confirmation.',
    )

    @api.depends('order_id.picking_id.move_line_ids',
                 'order_id.picking_id.move_line_ids.quantity_product_uom',
                 'product_id', 'expected_qty', 'is_service')
    def _compute_availability_state(self):
        for line in self:
            # Service/fee lines never need physical availability.
            if line.is_service or not line.product_id:
                line.available_qty = 0.0
                line.availability_state = 'available'
                continue
            picking = line.order_id.picking_id
            if not picking:
                line.available_qty = 0.0
                line.availability_state = 'not_available'
                continue
            reserved = sum(
                ml.quantity_product_uom for ml in picking.move_line_ids
                if ml.product_id.id == line.product_id.id
            )
            line.available_qty = reserved
            if reserved <= 0:
                line.availability_state = 'not_available'
            elif reserved < line.expected_qty:
                line.availability_state = 'partial'
            else:
                line.availability_state = 'available'
