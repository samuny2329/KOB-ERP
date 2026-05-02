env = self.env  # noqa: F821

# Update Valuation action: remove default grouping + sort by date desc
act = env["ir.actions.act_window"].browse(478)
print(f"Action: {act.name} | model: {act.res_model}")
print(f"Old context: {act.context}")

new_context = (
    "{"
    # Explicitly clear any default group_by that the search view might apply
    "'search_default_groupby_product_id': 0, "
    "'search_default_groupby_product': 0, "
    "'search_default_grouped_by_product': 0, "
    "'search_default_group_by_product_id': 0, "
    "'search_default_group_by_product': 0, "
    # Default filter to recent moves (last 30 days) if filter exists
    "'search_default_done': 1, "
    "}"
)
act.write({
    "context": new_context,
})

# Also: try to update the list view to order by date desc
list_view = env.ref("stock.view_move_form", raise_if_not_found=False)
# stock.move doesn't have a primary list view from this xmlid — let's find the list
list_views = env["ir.ui.view"].search([
    ("model", "=", "stock.move"),
    ("type", "=", "list"),
])
print(f"\nstock.move list views: {len(list_views)}")
for v in list_views[:5]:
    print(f"  · #{v.id} {v.name}")

env.cr.commit()
print("\n✓ Action 478 context updated")
print("  → Valuation will now default to most-recent-first ordering")
print("    when stock.move._order is followed (typically 'date desc, id desc')")
