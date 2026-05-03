# -*- coding: utf-8 -*-
"""Unified WMS user — every Odoo user can access KOB WMS.

PIN is stored on res.users so admins manage WMS access in one place
(Settings → Users) instead of a separate kob.wms.user record.
"""
import hashlib
import secrets

from odoo import api, fields, models


_PIN_SALT = "kob_wms_pin_2025"


class ResUsers(models.Model):
    _inherit = "res.users"

    wms_pin = fields.Char(
        string="WMS PIN",
        groups="base.group_user",
        copy=False,
        help="4-6 digit PIN for KOB WMS handheld login. "
             "Hashed automatically; never stored in plain text.")
    wms_pin_set = fields.Boolean(
        string="PIN Configured",
        compute="_compute_wms_pin_set", store=False)
    wms_role_label = fields.Char(
        string="WMS Role", compute="_compute_wms_role_label", store=False,
        help="Auto-detected from Odoo security groups.")

    @api.depends("wms_pin")
    def _compute_wms_pin_set(self):
        for r in self:
            r.wms_pin_set = bool(r.wms_pin)

    def _compute_wms_role_label(self):
        for r in self:
            for grp_xml, label in [
                ("kob_wms.group_wms_director",   "Director"),
                ("kob_wms.group_wms_manager",    "Manager"),
                ("kob_wms.group_wms_supervisor", "Supervisor"),
                ("kob_wms.group_wms_worker",     "Worker"),
            ]:
                grp = self.env.ref(grp_xml, raise_if_not_found=False)
                if grp and grp in r.group_ids:
                    r.wms_role_label = label
                    break
            else:
                r.wms_role_label = "User"

    def set_wms_pin(self, pin):
        """Hash + store PIN. Called from settings UI or Python."""
        for r in self:
            if not pin:
                r.write({"wms_pin": False})
                continue
            raw = (_PIN_SALT + str(pin).strip()).encode("utf-8")
            r.write({"wms_pin": hashlib.sha256(raw).hexdigest()})

    @api.model
    def _kob_wms_grant_all(self):
        """Backfill helper. Force-add every internal user to
        kob_wms.group_wms_worker so existing users gain access without
        needing the implied_ids dependency to propagate."""
        worker = self.env.ref(
            "kob_wms.group_wms_worker", raise_if_not_found=False)
        if not worker:
            return False
        users = self.sudo().search([("share", "=", False)])
        for u in users:
            if worker not in u.group_ids:
                u.write({"group_ids": [(4, worker.id)]})
        return True

    @api.model
    def authenticate_wms_pin(self, login, pin):
        """Look up user by login, verify PIN, return session info.

        Falls back to legacy kob.wms.user if no match on res.users — so
        existing handheld devices keep working during transition.
        """
        user = self.sudo().search([("login", "=", login)], limit=1)
        if not user:
            return {"ok": False, "reason": "user_not_found"}
        stored = user.wms_pin
        if not stored:
            # Legacy path
            WmsUser = self.env.get("kob.wms.user")
            if WmsUser is not None:
                return WmsUser.sudo().authenticate_pin(login, pin)
            return {"ok": False, "reason": "no_pin"}
        expected = hashlib.sha256(
            (_PIN_SALT + str(pin).strip()).encode("utf-8")).hexdigest()
        if not secrets.compare_digest(stored, expected):
            return {"ok": False, "reason": "wrong_pin"}
        return {
            "ok": True,
            "user_id": user.id,
            "name": user.name,
            "login": user.login,
            "role": user.wms_role_label,
        }
