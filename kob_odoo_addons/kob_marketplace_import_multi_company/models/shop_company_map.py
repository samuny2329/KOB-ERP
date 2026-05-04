"""Shop name → Company routing table.

Background: KOB's product catalogue is mostly shared across companies
(co_id NULL). The actual signal that determines which company should
own a marketplace order is the **shop name** in the import file (or
the resolved utm.source on existing SOs) — e.g. "Shopee_KissOfBeauty"
goes to KISS, "Shopee_Beautyville" goes to BTV, etc.

This table is the source of truth for that mapping. It can be:
* Seeded by hand (admin types each shop)
* Auto-learned by walking through existing sale.order records and
  voting on the most common (source_id.name → company_id) pair.

Used by `kob.marketplace.import.wizard.action_import` to route each
incoming order to the correct company.
"""
import logging
from collections import defaultdict

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WmsShopCompanyMap(models.Model):
    _name = "wms.shop.company.map"
    _description = "Marketplace Shop → Company routing"
    _order = "platform, shop_name"
    _rec_name = "shop_name"

    shop_name = fields.Char(
        required=True, index=True,
        help="Exact utm.source name as it appears on sale.order, "
             "e.g. 'Shopee_DaengGiMeoRi'.",
    )
    platform = fields.Selection(
        [
            ("shopee", "Shopee"),
            ("lazada", "Lazada"),
            ("tiktok", "TikTok"),
            ("odoo", "Odoo"),
            ("pos", "POS"),
            ("manual", "Manual"),
        ],
        help="Platform this shop belongs to (auto-derived from shop_name "
             "prefix when blank).",
    )
    company_id = fields.Many2one(
        "res.company", required=True, ondelete="restrict",
    )
    active = fields.Boolean(default=True)
    auto_learned = fields.Boolean(
        default=False,
        help="True if this row was created by the auto-learn cron from "
             "existing sale.order data. Manual edits flip this off so "
             "the cron does not overwrite the value next run.",
    )
    last_seen_so_count = fields.Integer(
        readonly=True,
        help="Vote count from the last auto-learn run.",
    )
    note = fields.Char()

    _sql_constraints = [
        (
            "shop_name_unique",
            "unique(shop_name)",
            "Shop name must be unique — already mapped.",
        ),
    ]

    @api.model
    def resolve(self, shop_name, allowed_companies=None):
        """Return res.company for a given shop_name. None if not mapped.
        If allowed_companies is given, only return a hit if the mapped
        company is in that recordset."""
        if not shop_name:
            return self.env["res.company"].browse()
        m = self.search([
            ("shop_name", "=", shop_name),
            ("active", "=", True),
        ], limit=1)
        if not m:
            return self.env["res.company"].browse()
        if allowed_companies and m.company_id not in allowed_companies:
            return self.env["res.company"].browse()
        return m.company_id

    # ------------------------------------------------------------------
    # Auto-learn from existing sale.order records
    # ------------------------------------------------------------------

    @api.model
    def cron_auto_learn(self):
        """Walk every sale.order with source_id set, count
        (source_name → company_id) pairs, then upsert this table.
        Manual rows (auto_learned=False) are NOT overwritten."""
        SO = self.env["sale.order"].sudo()
        votes = defaultdict(lambda: defaultdict(int))
        # source_id is a Many2one, so iterating is fine — but we batch
        # via search to keep it efficient on big DBs.
        for so in SO.search([("source_id", "!=", False)]):
            if not so.company_id:
                continue
            votes[so.source_id.name][so.company_id.id] += 1

        updated = 0
        created = 0
        skipped_manual = 0

        for shop_name, co_counts in votes.items():
            best_co_id = max(co_counts, key=lambda cid: co_counts[cid])
            best_n = co_counts[best_co_id]
            existing = self.search([("shop_name", "=", shop_name)], limit=1)

            if existing:
                if not existing.auto_learned:
                    skipped_manual += 1
                    continue
                # Update auto-learned row if vote winner changed
                if existing.company_id.id != best_co_id or existing.last_seen_so_count != best_n:
                    existing.write({
                        "company_id": best_co_id,
                        "last_seen_so_count": best_n,
                    })
                    updated += 1
            else:
                # Derive platform from prefix
                platform = False
                low = shop_name.lower()
                for p in ("shopee", "lazada", "tiktok", "odoo", "pos", "manual"):
                    if low.startswith(p):
                        platform = p
                        break
                self.create({
                    "shop_name": shop_name,
                    "platform": platform,
                    "company_id": best_co_id,
                    "auto_learned": True,
                    "last_seen_so_count": best_n,
                })
                created += 1

        _logger.info(
            "Shop→Company auto-learn: created=%s updated=%s skipped_manual=%s "
            "from %s distinct shops",
            created, updated, skipped_manual, len(votes),
        )
        return {"created": created, "updated": updated, "skipped": skipped_manual}

    def action_relearn(self):
        """Manual button to re-run the cron immediately."""
        result = self.cron_auto_learn()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Shop → Company re-learned"),
                "message": _(
                    "Created %(c)s, updated %(u)s, skipped %(s)s manual rows."
                ) % {"c": result["created"], "u": result["updated"],
                     "s": result["skipped"]},
                "type": "success",
                "sticky": False,
            },
        }
