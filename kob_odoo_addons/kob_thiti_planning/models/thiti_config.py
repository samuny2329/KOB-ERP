from odoo import fields, models


class ThitiConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    thiti_auto_create_po = fields.Boolean(
        string="Auto-create Purchase drafts",
        default=True,
        config_parameter="thiti.auto_create_po",
        help="Create draft purchase.order grouped by supplier+week.",
    )
    thiti_auto_create_mo = fields.Boolean(
        string="Auto-create Manufacturing drafts",
        default=True,
        config_parameter="thiti.auto_create_mo",
        help="Create draft mrp.production from solver proposed MOs.",
    )
    thiti_auto_create_do = fields.Boolean(
        string="Auto-create Distribution drafts",
        default=False,
        config_parameter="thiti.auto_create_do",
        help="Create draft stock.picking inter-warehouse transfers.",
    )
    thiti_po_horizon_days = fields.Integer(
        string="PO horizon (days)",
        default=30,
        config_parameter="thiti.po_horizon_days",
        help="Skip proposed POs scheduled beyond N days from today.",
    )
    thiti_mo_horizon_days = fields.Integer(
        string="MO horizon (days)",
        default=14,
        config_parameter="thiti.mo_horizon_days",
    )
    thiti_do_horizon_days = fields.Integer(
        string="DO horizon (days)",
        default=7,
        config_parameter="thiti.do_horizon_days",
    )
    thiti_delete_obsolete_drafts = fields.Boolean(
        string="Delete obsolete drafts on re-run",
        default=True,
        config_parameter="thiti.delete_obsolete_drafts",
        help="Cancel draft PO/MO/Picking from previous runs of the same name. "
             "Confirmed/sent docs are never touched.",
    )
    thiti_engine_binary_path = fields.Char(
        string="Engine binary path",
        default="/opt/thiti/bin/frepple",
        config_parameter="thiti.engine_binary_path",
    )
    thiti_engine_lib_dir = fields.Char(
        string="Engine library dir",
        default="/opt/thiti/lib",
        config_parameter="thiti.engine_lib_dir",
    )
    thiti_engine_timeout_sec = fields.Integer(
        string="Engine timeout (seconds)",
        default=600,
        config_parameter="thiti.engine_timeout_sec",
    )
