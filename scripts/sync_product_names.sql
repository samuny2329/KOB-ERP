-- Strip "— auto-imported" suffix + sync product_name across all modules
UPDATE product_template
SET name = jsonb_set(
    name, '{en_US}',
    to_jsonb(regexp_replace(name->>'en_US', '\s*[—-]+\s*auto[- ]imported\s*$', '', 'i'))
)
WHERE name->>'en_US' ~* 'auto[- ]imported';

UPDATE wms_sales_order_line l
SET product_name = '[' || pp.default_code || '] ' || (pt.name->>'en_US')
FROM product_product pp
JOIN product_template pt ON pt.id = pp.product_tmpl_id
WHERE l.product_id = pp.id
  AND pp.default_code IS NOT NULL;

UPDATE stock_move sm
SET description_picking = '[' || pp.default_code || '] ' || (pt.name->>'en_US')
FROM product_product pp
JOIN product_template pt ON pt.id = pp.product_tmpl_id
WHERE sm.product_id = pp.id
  AND pp.default_code IS NOT NULL
  AND (sm.description_picking IS NULL OR sm.description_picking = ''
       OR sm.description_picking ILIKE '%auto-imported%');

SELECT 'product_template still auto-imported' AS m, COUNT(*) FROM product_template WHERE name->>'en_US' ILIKE '%auto-imported%';
SELECT 'wms_sales_order_line still auto-imported' AS m, COUNT(*) FROM wms_sales_order_line WHERE product_name ILIKE '%auto-imported%';
SELECT 'stock_move still auto-imported' AS m, COUNT(*) FROM stock_move WHERE description_picking ILIKE '%auto-imported%';

SELECT default_code, name->>'en_US' AS name FROM product_template
WHERE default_code IN ('KLAP200','KICM050','SWB700','DUT300','STDH010') ORDER BY default_code;
