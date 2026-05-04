"""Multi-company validation override for the marketplace import wizard.

Phase 1 behaviour (this commit):
* Override `_resolve_product` so that, when the new
  `enforce_product_company` flag is on, products without on-hand stock
  in the wizard's selected company are treated as "not found" — the
  parent's existing "WARN — SKU not found" message fires and the line
  is skipped from SO creation.
* Add a wizard checkbox to toggle the behaviour.
* Add a separate `restrict_to_active_companies` flag that broadens the
  acceptable home companies to anything in the user's company switcher
  (env.companies) rather than only the wizard's primary company.

Phase 2 (planned, NOT in this commit):
* Auto-route SO to the product's home company instead of skipping —
  effectively splitting orders that span multiple companies into one
  SO per company.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class MarketplaceImportWizard(models.TransientModel):
    _inherit = "kob.marketplace.import.wizard"

    enforce_product_company = fields.Boolean(
        string="Skip products not stocked in this company",
        default=True,
        help=(
            "When enabled, only SKUs that actually have on-hand stock in "
            "the selected company (or in any active-switcher company if "
            "'Use the company switcher' is on) will land in the SO. "
            "Out-of-company SKUs raise a warning and are skipped — they "
            "do not silently create a misrouted SO."
        ),
    )
    restrict_to_active_companies = fields.Boolean(
        string="Allow any active company",
        default=False,
        help=(
            "Off (default): a product must have stock in the wizard's "
            "primary company. On: a product is acceptable if it has "
            "stock in ANY company currently ticked in the user's "
            "company switcher (`self.env.companies`)."
        ),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _kob_allowed_companies(self):
        if self.restrict_to_active_companies:
            return self.env.companies or self.company_id
        return self.company_id

    def _kob_product_has_stock(self, product, allowed_companies):
        """True if `product` has > 0 on-hand qty in an internal location
        of any company in `allowed_companies`."""
        if not product or not allowed_companies:
            return False
        Quant = self.env["stock.quant"].sudo()
        return bool(Quant.search_count([
            ("product_id", "=", product.id),
            ("location_id.usage", "=", "internal"),
            ("company_id", "in", allowed_companies.ids),
            ("quantity", ">", 0),
        ]))

    def _kob_product_home_company(self, product, allowed_companies):
        """Return res.company holding the most stock for `product`
        among `allowed_companies`. Used by callers that want to route,
        not just validate."""
        Quant = self.env["stock.quant"].sudo()
        per_company = {}
        for q in Quant.search([
            ("product_id", "=", product.id),
            ("location_id.usage", "=", "internal"),
            ("company_id", "in", allowed_companies.ids),
            ("quantity", ">", 0),
        ]):
            per_company[q.company_id.id] = (
                per_company.get(q.company_id.id, 0) + q.quantity
            )
        if not per_company:
            return self.env["res.company"].browse()
        if self.company_id and self.company_id.id in per_company:
            return self.company_id
        best = max(per_company, key=lambda cid: per_company[cid])
        return self.env["res.company"].browse(best)

    # ------------------------------------------------------------------
    # Override product resolver — silently fail when out-of-company
    # ------------------------------------------------------------------

    def _resolve_product(self, sku, brand=None):
        product = super()._resolve_product(sku, brand)
        if not self.enforce_product_company or not product:
            return product

        allowed = self._kob_allowed_companies()
        if self._kob_product_has_stock(product, allowed):
            return product

        # Product exists globally but has no stock in any allowed company.
        # Find where it DOES live so the log can tell the user clearly.
        all_companies = self.env["res.company"].sudo().search([])
        elsewhere = self._kob_product_home_company(product, all_companies)
        if elsewhere:
            _logger.warning(
                "Marketplace import: SKU %s exists in %s but not in any "
                "allowed company %s — skipping line.",
                sku, elsewhere.name, allowed.mapped("name"),
            )
        else:
            _logger.warning(
                "Marketplace import: SKU %s exists but has no on-hand "
                "stock anywhere — skipping line.", sku,
            )
        # Returning False makes the parent log "WARN — SKU not found"
        # and skip the line; that's the "ขึ้นฟ้อง" the user asked for.
        # We also append a more specific note to import_log so the user
        # sees exactly which company actually owns the product.
        if elsewhere:
            extra = _(
                "⚠ SKU %(sku)s exists in %(co)s but is out of stock in "
                "allowed companies (%(allowed)s). Line skipped."
            ) % {
                "sku": sku,
                "co": elsewhere.name,
                "allowed": ", ".join(allowed.mapped("name")) or "(none)",
            }
            self.log = (self.log or "") + extra + "\n"
        return self.env["product.product"]
