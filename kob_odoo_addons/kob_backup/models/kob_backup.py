# -*- coding: utf-8 -*-
"""KOB Backup — daily DB dump + retention.

Strategy:
  - Each day, call Odoo's odoo.service.db.dump_db() to write a .zip backup
  - Save to /var/lib/odoo/backups (configurable)
  - Retain last N days, delete older
  - Log every attempt to kob.backup.log
"""
import logging
import os
import datetime
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class KobBackupConfig(models.Model):
    _name = "kob.backup.config"
    _description = "Backup Configuration"

    name = fields.Char(default="Default", required=True)
    backup_dir = fields.Char(
        default="/var/lib/odoo/backups", required=True,
        help="Filesystem path inside the Odoo container.",
    )
    retention_days = fields.Integer(default=14)
    active = fields.Boolean(default=True)

    @api.model
    def cron_run_backup(self):
        """Cron entrypoint — backup every active config."""
        for cfg in self.search([("active", "=", True)]):
            cfg.action_do_backup()

    def action_do_backup(self):
        from odoo.service import db
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            today = datetime.date.today().isoformat()
            db_name = self.env.cr.dbname
            filename = f"{db_name}-{today}.zip"
            filepath = os.path.join(self.backup_dir, filename)
            if os.path.exists(filepath):
                _logger.info("Backup %s exists, skipping", filename)
                return
            with open(filepath, "wb") as f:
                db.dump_db(db_name, f, backup_format="zip")
            size_mb = os.path.getsize(filepath) / 1024 / 1024
            self.env["kob.backup.log"].sudo().create({
                "config_id": self.id,
                "filename": filename,
                "filepath": filepath,
                "size_mb": size_mb,
                "success": True,
            })
            _logger.info("Backup written: %s (%.2f MB)", filename, size_mb)
            # Retention cleanup
            self._cleanup_old_backups()
        except Exception as e:
            self.env["kob.backup.log"].sudo().create({
                "config_id": self.id,
                "filename": "(failed)",
                "error": str(e)[:5000],
                "success": False,
            })
            _logger.error("Backup failed: %s", e)

    def _cleanup_old_backups(self):
        cutoff = datetime.date.today() - datetime.timedelta(days=self.retention_days)
        if not os.path.isdir(self.backup_dir):
            return
        for f in os.listdir(self.backup_dir):
            if not f.endswith(".zip"):
                continue
            full = os.path.join(self.backup_dir, f)
            mtime = datetime.date.fromtimestamp(os.path.getmtime(full))
            if mtime < cutoff:
                os.remove(full)
                _logger.info("Pruned old backup: %s", f)


class KobBackupLog(models.Model):
    _name = "kob.backup.log"
    _description = "Backup Log"
    _order = "create_date desc"

    config_id = fields.Many2one("kob.backup.config", ondelete="cascade")
    filename = fields.Char()
    filepath = fields.Char()
    size_mb = fields.Float()
    success = fields.Boolean()
    error = fields.Text()
    create_date = fields.Datetime(readonly=True)
