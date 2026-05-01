# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

ROLE_PAGES = {
    'admin': {'dashboard', 'picking', 'packing', 'scan', 'dispatch', 'inventory', 'recon', 'kpi', 'users'},
    'supervisor': {'dashboard', 'picking', 'packing', 'scan', 'dispatch', 'inventory', 'recon', 'kpi'},
    'picker': {'dashboard', 'picking', 'inventory'},
    'packer': {'dashboard', 'packing'},
    'outbound': {'dashboard', 'scan', 'dispatch'},
    'coordinator': {'dashboard', 'recon', 'kpi'},
    'viewer': {'dashboard', 'kpi'},
}


class KobWmsPortal(http.Controller):

    def _get_user(self):
        token = request.httprequest.cookies.get('kob_token')
        if not token:
            return False
        return request.env['kob.wms.user'].verify_token(token)

    def _check_access(self, page):
        user = self._get_user()
        if not user:
            return None, request.redirect('/kob/login')
        if page not in ROLE_PAGES.get(user.role, set()):
            return user, request.redirect('/kob/dashboard?error=no_access')
        return user, None

    # ── Login / Logout ──

    @http.route('/kob/login', type='http', auth='public', website=False, csrf=False, methods=['GET'])
    def login_page(self, **kw):
        user = self._get_user()
        if user:
            return request.redirect('/kob/dashboard')
        return request.render('kob_wms.kob_login_page', {'error': kw.get('error', '')})

    @http.route('/kob/login', type='http', auth='public', website=False, csrf=False, methods=['POST'])
    def login_submit(self, username=None, password=None, pin=None, **kw):
        WmsUser = request.env['kob.wms.user']
        if pin and username:
            result = WmsUser.authenticate_pin(username, pin)
        elif username and password:
            result = WmsUser.authenticate(username, password)
        else:
            return request.redirect('/kob/login?error=missing_fields')

        if not result:
            return request.redirect('/kob/login?error=invalid')

        resp = request.redirect('/kob/dashboard')
        resp.set_cookie('kob_token', result['token'], max_age=8 * 3600, httponly=True, samesite='Lax')
        resp.set_cookie('kob_user', json.dumps({'name': result['name'], 'role': result['role']}),
                        max_age=8 * 3600, samesite='Lax')
        return resp

    @http.route('/kob/api/pin', type='json', auth='public', methods=['POST'], csrf=False)
    def api_authenticate_pin(self, username='', pin='', **kw):
        """JSON endpoint for PIN login — bypasses ORM call permission checks."""
        try:
            result = request.env['kob.wms.user'].sudo().authenticate_pin(username, str(pin))
            return result
        except Exception as e:
            _logger.exception("api_authenticate_pin error: %s", e)
            return {'ok': False, 'reason': 'server_error', 'message': str(e)}

    @http.route('/kob/admin/reset-pins', type='http', auth='user', website=False, csrf=False)
    def reset_pins(self, **kw):
        """One-shot: reset every active WMS user's PIN to 1234 (SHA256 hash)."""
        import hashlib
        PIN_SALT = 'kob_wms_pin_2025'
        new_hash = hashlib.sha256((PIN_SALT + '1234').encode()).hexdigest()
        users = request.env['kob.wms.user'].sudo().search([('is_active', '=', True)])
        users.write({'pin': new_hash})
        names = ', '.join(users.mapped('name')) or '(none)'
        _logger.info("reset-pins: updated %s users to SHA256 hash of 1234", len(users))
        return Response(
            f"<h2>✅ Done — reset {len(users)} users to PIN 1234</h2>"
            f"<p>Users: {names}</p>"
            f"<p>Go back to the WMS login screen and enter PIN <strong>1234</strong>.</p>",
            content_type='text/html'
        )

    @http.route('/kob/logout', type='http', auth='public', website=False, csrf=False)
    def logout(self, **kw):
        user = self._get_user()
        if user:
            user.logout()
        resp = request.redirect('/kob/login')
        resp.delete_cookie('kob_token')
        resp.delete_cookie('kob_user')
        return resp

    # ── Dashboard ──

    @http.route('/kob/dashboard', type='http', auth='public', website=False, csrf=False)
    def dashboard(self, **kw):
        user, redirect = self._check_access('dashboard')
        if redirect:
            return redirect

        SO = request.env['wms.sales.order'].sudo()
        stats = {
            'pending': SO.search_count([('status', '=', 'pending')]),
            'picking': SO.search_count([('status', '=', 'picking')]),
            'packed': SO.search_count([('status', '=', 'packed')]),
            'shipped': SO.search_count([('status', '=', 'shipped')]),
        }
        return request.render('kob_wms.kob_dashboard_page', {
            'user': user,
            'stats': stats,
            'pages': ROLE_PAGES.get(user.role, set()),
            'error': kw.get('error', ''),
        })

    # ── Picking ──

    @http.route('/kob/picking', type='http', auth='public', website=False, csrf=False)
    def picking_list(self, **kw):
        user, redirect = self._check_access('picking')
        if redirect:
            return redirect

        orders = request.env['wms.sales.order'].sudo().search(
            [('status', '=', 'pending')], order='create_date desc', limit=50)
        return request.render('kob_wms.kob_picking_page', {
            'user': user, 'orders': orders, 'pages': ROLE_PAGES.get(user.role, set()),
        })

    # ── Packing ──

    @http.route('/kob/packing', type='http', auth='public', website=False, csrf=False)
    def packing_list(self, **kw):
        user, redirect = self._check_access('packing')
        if redirect:
            return redirect

        orders = request.env['wms.sales.order'].sudo().search(
            [('status', '=', 'picked')], order='create_date desc', limit=50)
        return request.render('kob_wms.kob_packing_page', {
            'user': user, 'orders': orders, 'pages': ROLE_PAGES.get(user.role, set()),
        })

    # ── JSON API (for handheld AJAX) ──

    @http.route('/kob/api/me', type='json', auth='public', csrf=False)
    def api_me(self, **kw):
        user = self._get_user()
        if not user:
            return {'error': 'unauthorized'}
        return {'id': user.id, 'name': user.name, 'role': user.role,
                'pages': list(ROLE_PAGES.get(user.role, set()))}
