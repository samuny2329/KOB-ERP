# -*- coding: utf-8 -*-
"""Role → source mapping for My Battle Board.

Each record says: "if user has THIS role/group, enable THESE source
collectors". Multiple rules can apply to the same user — their source
sets are unioned.
"""
from odoo import api, fields, models


SOURCE_KEYS = [
    ("approval",   "Approval Steps"),
    ("helpdesk",   "Helpdesk Tickets"),
    ("field_svc",  "Field Service Tasks"),
    ("wms_count",  "WMS Count Tasks"),
    ("kpi",        "KPI Assessments"),
    ("returns",    "RMA / Returns"),
    ("ocr_review", "Invoice OCR Review"),
    ("activities", "Mail Activities"),
    ("ai",         "AI Suggestions"),
]


class KobMyTaskRoleSourceMap(models.Model):
    _name = "kob.my.task.role.source.map"
    _description = "My Battle Board — Role to Sources mapping"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ── Trigger conditions (any of these matches enables sources) ──────
    wms_role = fields.Selection(
        [("admin",       "Admin"),
         ("supervisor",  "Supervisor"),
         ("picker",      "Picker"),
         ("packer",      "Packer"),
         ("outbound",    "Outbound"),
         ("coordinator", "Coordinator"),
         ("viewer",      "Viewer")],
        help="If set, this rule applies when the user has a "
             "kob.wms.user record with this role.",
    )
    odoo_group_id = fields.Many2one(
        "res.groups",
        string="Odoo Security Group",
        help="If set, this rule applies when the user belongs to this "
             "Odoo security group (e.g. group_wms_manager).",
    )
    is_default = fields.Boolean(
        default=False,
        help="If set, this rule applies to ALL users (e.g. baseline "
             "Activities + own Helpdesk).",
    )

    # ── Sources to enable ────────────────────────────────────────────────
    enable_approval = fields.Boolean()
    enable_helpdesk = fields.Boolean()
    enable_field_svc = fields.Boolean()
    enable_wms_count = fields.Boolean()
    enable_kpi = fields.Boolean()
    enable_returns = fields.Boolean()
    enable_ocr_review = fields.Boolean()
    enable_activities = fields.Boolean(default=True)
    enable_ai = fields.Boolean()

    note = fields.Text()

    # ────────────────────────────────────────────────────────────────────
    @api.model
    def keys_for_user(self, user):
        """Return a set of source keys enabled for `user` based on all
        matching rules (union)."""
        keys = set()
        rules = self.search([("active", "=", True)])

        # Find user's wms.role if any
        wms_role = None
        WmsUser = self.env.get("kob.wms.user")
        if WmsUser is not None:
            kob_user = WmsUser.search(
                [("res_user_id", "=", user.id)], limit=1)
            if kob_user:
                wms_role = kob_user.role

        for r in rules:
            applies = False
            if r.is_default:
                applies = True
            if r.wms_role and r.wms_role == wms_role:
                applies = True
            if r.odoo_group_id and r.odoo_group_id in user.groups_id:
                applies = True

            if not applies:
                continue
            if r.enable_approval:    keys.add("approval")
            if r.enable_helpdesk:    keys.add("helpdesk")
            if r.enable_field_svc:   keys.add("field_svc")
            if r.enable_wms_count:   keys.add("wms_count")
            if r.enable_kpi:         keys.add("kpi")
            if r.enable_returns:     keys.add("returns")
            if r.enable_ocr_review:  keys.add("ocr_review")
            if r.enable_activities:  keys.add("activities")
            if r.enable_ai:          keys.add("ai")
        return keys
