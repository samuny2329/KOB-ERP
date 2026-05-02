#!/usr/bin/env python3
"""Bulk-enable res.config.settings across all installed apps.

Strategy: instantiate res.config.settings, write a dict of feature flags
that are valid in Community (no Enterprise badge), execute the wizard.
"""

env = self.env  # noqa: F821

# All bool settings worth enabling — grouped by app for clarity.
# Field name validation: only set if the field exists on res.config.settings.
SETTINGS_FLAGS = {
    # === Purchase ===
    "po_lock": "lock",                                    # Lock Confirmed Orders
    "group_warning_purchase": True,                        # Warnings
    "group_send_reminder": True,                           # Receipt Reminder
    "po_double_validation": "two_step",                    # Purchase Order Approval
    "po_double_validation_amount": 5000.0,                 # threshold
    "group_purchase_alternatives": True,                   # Alternative POs
    "module_purchase_requisition": True,                   # Purchase Agreements
    # === Inventory / Stock ===
    "group_stock_adv_location": True,                      # Multi-Step Routes
    "group_stock_multi_warehouses": True,
    "group_stock_packaging": True,                         # Packaging
    "group_stock_storage_categories": True,                # Storage Categories
    "group_stock_tracking_lot": True,                      # Track lots
    "group_stock_tracking_owner": True,                    # Owner stock
    "group_stock_production_lot": True,                    # Lots/Serials
    "group_lot_on_delivery_slip": True,                    # Show lots on DO
    "group_warning_stock": True,                           # Stock warnings
    "group_stock_picking_wave": True,                      # Wave Transfers
    "module_stock_landed_costs": True,                     # Landed Costs
    "module_stock_dropshipping": True,                     # Dropshipping
    "module_quality_control": False,                       # Enterprise (skip)
    "module_stock_barcode": False,                         # Enterprise (skip)
    "use_propagation_minimum_delta": True,
    "use_security_lead": True,
    "security_lead": 1.0,
    "use_po_lead": True,
    "po_lead": 1.0,
    # === Manufacturing ===
    "group_mrp_routings": True,                            # Work Orders
    "module_mrp_subcontracting": True,                     # Subcontracting
    "group_mrp_byproducts": True,                          # By-products
    "group_unlocked_by_default": True,                     # MO unlocked
    "group_mrp_workorder_dependencies": True,
    "module_mrp_plm": False,                               # Enterprise
    "module_quality_mrp": False,                           # Enterprise
    "module_mrp_workorder": False,                         # Enterprise tablet view
    # === Sales ===
    "group_show_price_total": True,
    "group_uom": True,                                     # UoM on sales lines
    "group_discount_per_so_line": True,                    # Discount column
    "group_warning_sale": True,                            # Sale warnings
    "group_sale_pricelist": True,
    "group_product_pricelist": True,                       # Pricelists
    "module_sale_loyalty": True,                           # Loyalty + Coupons
    "module_delivery": True,                               # Delivery methods
    "module_sale_margin": True,                            # Margin column
    "module_sale_subscription": False,                     # Enterprise
    "automatic_invoice": False,
    # === Accounting ===
    "group_multi_currency": True,
    "group_analytic_accounting": True,
    "group_cash_rounding": True,
    "tax_calculation_rounding_method": "round_per_line",
    "group_show_line_subtotals_tax_excluded": True,
    "module_account_check_printing": True,
    "module_account_followup": True,                       # Customer follow-up
    "module_account_payment": True,
    "module_account_reports": False,                       # Enterprise
    "module_account_accountant": False,                    # Enterprise
    "module_account_intrastat": False,                     # Enterprise
    # === CRM ===
    "group_use_lead": True,                                # Leads
    "module_crm_iap_enrich": False,                        # Enterprise
}

# Filter to fields that actually exist on res.config.settings
all_fields = env["res.config.settings"]._fields
applicable = {
    k: v for k, v in SETTINGS_FLAGS.items()
    if k in all_fields
}
skipped = sorted(set(SETTINGS_FLAGS) - set(applicable))
print(f"Settings to apply: {len(applicable)}")
print(f"Settings skipped (field absent): {len(skipped)}")
for s in skipped[:8]:
    print(f"  · skipped: {s}")

# Execute as superuser
config = env["res.config.settings"].sudo().create(applicable)
config.execute()
env.cr.commit()
print(f"\n✓ res.config.settings.execute() OK — wrote {len(applicable)} flags")

# Reload + verify a few
print("\n=== Spot check ===")
ICP = env["ir.config_parameter"].sudo()
groups = env["res.groups"]
checks = [
    ("group_stock_storage_categories", "stock.group_stock_storage_categories"),
    ("group_stock_adv_location",       "stock.group_adv_location"),
    ("group_mrp_routings",             "mrp.group_mrp_routings"),
    ("group_discount_per_so_line",     "product.group_discount_per_so_line"),
]
for fname, gxml in checks:
    try:
        g = env.ref(gxml)
        # Check if implied by base.group_user
        is_implied = env.ref("base.group_user").id in g.trans_implied_ids.ids or \
                     g.id in env.ref("base.group_user").trans_implied_ids.ids
        n_users = env.cr.execute(
            "SELECT COUNT(*) FROM res_groups_users_rel WHERE gid = %s", (g.id,),
        )
        print(f"  {fname:42s} group exists ✓")
    except Exception as e:
        print(f"  {fname:42s} {e!r}"[:120])
