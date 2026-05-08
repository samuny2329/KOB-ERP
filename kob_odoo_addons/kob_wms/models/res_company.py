# -*- coding: utf-8 -*-
"""Company-level toggles for KOB WMS.

Currently provides:
    wms_skip_pack — temporary mode where Pack stage is bypassed.
                    OUT step does invoice + stock cut. Used when the
                    physical pack/scan station is offline. Toggle off
                    when scanner is back to resume Pick → Pack → Out.
"""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    wms_skip_pack = fields.Boolean(
        string="Skip Pack stage",
        default=False,
        help="When ON, the Pack screen is bypassed. Picked orders flow "
             "directly to Outbound, where stock validation and invoice "
             "creation are performed. Use temporarily when the pack "
             "scanner station is unavailable. Turn OFF to restore the "
             "normal Pick → Pack → Out workflow.",
    )

    wms_skip_dispatch_scan = fields.Boolean(
        string="Skip Dispatch AWB scan",
        default=False,
        help="When ON, the Dispatch screen does not require manually "
             "scanning each AWB into the courier batch. The batch's "
             "'Auto-Fill from Packed' action collects all packed/shipped "
             "SOs assigned to the batch's courier and links their AWBs "
             "in one step. Receiver signature is still required. Use "
             "when the worker trusts the courier driver and the AWB list "
             "is verified by paperwork instead of barcode.",
    )
