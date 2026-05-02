# -*- coding: utf-8 -*-
"""Phase 47 — Rate-limited API controller (sample endpoints + middleware)."""
import json
import time

from odoo import http
from odoo.http import request, Response


class KobApiController(http.Controller):

    def _authenticate_and_check(self, endpoint):
        """Returns (api_key_record, error_response_or_None)."""
        key = request.httprequest.headers.get("X-KOB-API-Key")
        if not key:
            return None, self._json(401, {"error": "missing_api_key"})
        ApiKey = request.env["kob.api.key"].sudo()
        rec = ApiKey.search([("key", "=", key), ("active", "=", True)], limit=1)
        if not rec:
            return None, self._json(401, {"error": "invalid_api_key"})
        if rec.expires_at and rec.expires_at < http.fields.Datetime.now():
            return None, self._json(401, {"error": "expired_api_key"})
        Limiter = request.env["kob.api.rate.limit"].sudo()
        if not Limiter.check_and_increment(rec, endpoint=endpoint):
            return rec, self._json(429, {
                "error": "rate_limited",
                "limit_rpm": rec.rate_limit_rpm,
            })
        return rec, None

    def _log(self, rec, endpoint, method, status, started, error=""):
        try:
            request.env["kob.api.call.log"].sudo().create({
                "api_key_id": rec.id if rec else False,
                "user_id": rec.user_id.id if rec else False,
                "endpoint": endpoint,
                "method": method,
                "status_code": status,
                "duration_ms": int((time.time() - started) * 1000),
                "ip_address": request.httprequest.remote_addr,
                "user_agent": request.httprequest.headers.get("User-Agent", "")[:255],
                "error_message": error or "",
            })
        except Exception:
            pass

    def _json(self, status, payload):
        return Response(json.dumps(payload), status=status,
                        content_type="application/json")

    @http.route("/api/v1/kob/ping", type="http", auth="public",
                methods=["GET"], csrf=False)
    def ping(self, **kw):
        started = time.time()
        rec, err = self._authenticate_and_check("/api/v1/kob/ping")
        if err:
            self._log(rec, "/api/v1/kob/ping", "GET",
                      err.status_code, started, error="auth_or_rate")
            return err
        resp = self._json(200, {"ok": True, "ts": int(time.time())})
        self._log(rec, "/api/v1/kob/ping", "GET", 200, started)
        return resp

    @http.route("/api/v1/kob/me", type="http", auth="public",
                methods=["GET"], csrf=False)
    def me(self, **kw):
        started = time.time()
        rec, err = self._authenticate_and_check("/api/v1/kob/me")
        if err:
            return err
        resp = self._json(200, {
            "key_name": rec.name,
            "user": rec.user_id.login,
            "rate_limit_rpm": rec.rate_limit_rpm,
            "calls_total": rec.call_count,
        })
        self._log(rec, "/api/v1/kob/me", "GET", 200, started)
        return resp
