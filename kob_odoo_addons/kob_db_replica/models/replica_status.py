from odoo import api, fields, models, _

from ..replica_router import _get_replica_uri, _open_replica_connection, replica_lag_seconds


class KobReplicaStatus(models.TransientModel):
    """Diagnostic dashboard for the read replica."""

    _name = "kob.replica.status"
    _description = "KOB DB Replica Status"

    is_configured = fields.Boolean(compute="_compute_status")
    replica_dsn = fields.Char(compute="_compute_status")
    is_reachable = fields.Boolean(compute="_compute_status")
    lag_seconds = fields.Float(compute="_compute_status")
    last_check = fields.Datetime(compute="_compute_status")
    health = fields.Selection(
        [("ok", "OK"), ("warn", "Warning"), ("fail", "Failure"), ("disabled", "Not configured")],
        compute="_compute_status",
    )

    @api.depends_context("uid")
    def _compute_status(self):
        for r in self:
            uri = _get_replica_uri()
            r.last_check = fields.Datetime.now()
            if not uri:
                r.is_configured = False
                r.replica_dsn = ""
                r.is_reachable = False
                r.lag_seconds = 0.0
                r.health = "disabled"
                continue
            r.is_configured = True
            # Show only the host:port part — never expose password
            try:
                from urllib.parse import urlparse
                p = urlparse(uri)
                r.replica_dsn = f"{p.scheme}://{p.hostname}:{p.port}/{(p.path or '').lstrip('/')}"
            except Exception:
                r.replica_dsn = "[BLOCKED]"
            conn = _open_replica_connection()
            if not conn:
                r.is_reachable = False
                r.lag_seconds = 0.0
                r.health = "fail"
                continue
            r.is_reachable = True
            try:
                conn.close()
            except Exception:
                pass
            lag = replica_lag_seconds()
            r.lag_seconds = lag or 0.0
            if lag is None:
                r.health = "warn"
            elif lag < 5:
                r.health = "ok"
            elif lag < 30:
                r.health = "warn"
            else:
                r.health = "fail"
