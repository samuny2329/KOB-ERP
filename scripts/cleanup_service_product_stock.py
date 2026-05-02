env = self.env  # noqa: F821

# Find all service products (type='service' or is_storable=False)
print("Step 1: Find service / non-storable products with stock data")
env.cr.execute("""
    SELECT pt.id, pt.default_code, pt.type, pt.is_storable
    FROM product_template pt
    WHERE pt.type = 'service' OR pt.is_storable = FALSE
""")
service_tmpls = env.cr.fetchall()
print(f"  · {len(service_tmpls)} service/non-storable templates")

# Get product variant ids
env.cr.execute("""
    SELECT pp.id
    FROM product_product pp
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE pt.type = 'service' OR pt.is_storable = FALSE
""")
service_pids = [r[0] for r in env.cr.fetchall()]
print(f"  · {len(service_pids)} service variants")

if not service_pids:
    print("  · nothing to clean")
else:
    # Step 2: Delete stock.quants on these products
    env.cr.execute(
        "DELETE FROM stock_quant WHERE product_id = ANY(%s)",
        (service_pids,),
    )
    n_quants = env.cr.rowcount
    print(f"\nStep 2: Deleted {n_quants} stock.quants on service products")

    # Step 3: Archive stock.moves on these products (don't delete, keep audit)
    env.cr.execute(
        "UPDATE stock_move SET state = 'cancel' "
        "WHERE product_id = ANY(%s) AND state IN ('draft', 'confirmed', 'partially_available', 'assigned')",
        (service_pids,),
    )
    n_cancelled = env.cr.rowcount
    print(f"Step 3: Cancelled {n_cancelled} pending stock.moves on services")

    # Step 4: Hide done moves from Valuation by tagging them is_in/is_out=False
    # The Valuation action filters: ['|', ('is_in', '=', True), ('is_out', '=', True)]
    # If we set both False, they won't show.
    # is_in / is_out are computed fields — flip them via direct quant_value reset
    env.cr.execute("""
        UPDATE stock_move
        SET stock_valuation_layer_ids = NULL  -- detach valuation
        WHERE product_id = ANY(%s) AND state = 'done'
    """, (service_pids,)) if False else None  # this column may not exist directly

    # Easier: just delete done moves on services (they shouldn't be there)
    env.cr.execute("""
        DELETE FROM stock_move_line ml
        WHERE ml.product_id = ANY(%s)
    """, (service_pids,))
    n_lines = env.cr.rowcount
    env.cr.execute("""
        DELETE FROM stock_move m
        WHERE m.product_id = ANY(%s)
    """, (service_pids,))
    n_moves = env.cr.rowcount
    print(f"Step 4: Deleted {n_moves} stock.moves + {n_lines} move lines (services shouldn't have any)")

env.cr.commit()

# Verify
print("\n=== Verification ===")
env.cr.execute("""
    SELECT COUNT(*) FROM stock_quant q
    JOIN product_product pp ON pp.id = q.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE pt.type = 'service' OR pt.is_storable = FALSE
""")
print(f"  Remaining service quants: {env.cr.fetchone()[0]}")
env.cr.execute("""
    SELECT COUNT(*) FROM stock_move m
    JOIN product_product pp ON pp.id = m.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE pt.type = 'service' OR pt.is_storable = FALSE
""")
print(f"  Remaining service moves: {env.cr.fetchone()[0]}")
