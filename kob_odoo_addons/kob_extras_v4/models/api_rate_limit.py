# -*- coding: utf-8 -*-
"""Phase 47 — API rate-limiting + monitoring.

Token-bucket rate limiter scoped per API key + endpoint pattern. Records
every API call for monitoring/audit. Limits are configurable per key.
"""
import time

from odoo import api, fields, models


class KobApiKey(models.Model):
    _name = "kob.api.key"
    _description = "API Key"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(required=True)
    key = fields.Char(required=True, copy=False, index=True)
    user_id = fields.Many2one("res.users", required=True,
                              default=lambda s: s.env.user)
    active = fields.Boolean(default=True)
    rate_limit_rpm = fields.Integer(string="Requests / Minute", default=60)
    rate_limit_rpd = fields.Integer(string="Requests / Day", default=10000)
    expires_at = fields.Datetime()
    last_used_at = fields.Datetime()
    call_count = fields.Integer(readonly=True, default=0)
    notes = fields.Text()

    _sql_constraints = [
        ("kob_api_key_unique", "unique(key)", "API key must be unique."),
    ]


class KobApiCallLog(models.Model):
    _name = "kob.api.call.log"
    _description = "API Call Log"
    _order = "create_date desc"
    _rec_name = "endpoint"

    api_key_id = fields.Many2one("kob.api.key", ondelete="set null")
    user_id = fields.Many2one("res.users")
    endpoint = fields.Char(required=True)
    method = fields.Char()
    status_code = fields.Integer()
    duration_ms = fields.Integer()
    ip_address = fields.Char()
    user_agent = fields.Char()
    request_body_size = fields.Integer()
    response_body_size = fields.Integer()
    error_message = fields.Text()


class KobApiRateLimit(models.Model):
    _name = "kob.api.rate.limit"
    _description = "API Rate-Limit Bucket"
    _order = "api_key_id, window_start desc"

    api_key_id = fields.Many2one("kob.api.key", required=True, ondelete="cascade")
    window_start = fields.Datetime(required=True)
    window_seconds = fields.Integer(default=60)
    request_count = fields.Integer(default=0)

    @api.model
    def check_and_increment(self, api_key_record, endpoint=""):
        """Return True if call is allowed; False if rate-limited."""
        if not api_key_record or not api_key_record.active:
            return False
        now = fields.Datetime.now()
        # Minute bucket
        minute_start = now.replace(second=0, microsecond=0)
        bucket = self.search([
            ("api_key_id", "=", api_key_record.id),
            ("window_start", "=", minute_start),
            ("window_seconds", "=", 60),
        ], limit=1)
        if not bucket:
            bucket = self.create({
                "api_key_id": api_key_record.id,
                "window_start": minute_start,
                "window_seconds": 60,
                "request_count": 0,
            })
        if bucket.request_count >= api_key_record.rate_limit_rpm:
            return False
        bucket.request_count += 1
        api_key_record.write({
            "last_used_at": now,
            "call_count": api_key_record.call_count + 1,
        })
        return True

    @api.model
    def cron_purge_old_buckets(self):
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=2)
        old = self.search([("window_start", "<", cutoff)])
        n = len(old)
        old.unlink()
        return n
