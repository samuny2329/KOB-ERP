-- Strip the leading "[SKU] " prefix from product_template.name (jsonb)
-- so Odoo's display_name doesn't show "[SKU] [SKU] …" duplicates.
UPDATE product_template
SET name = jsonb_set(
    name,
    '{en_US}',
    to_jsonb(
        regexp_replace(name->>'en_US', '^\[' || default_code || '\]\s*', '')
    )
)
WHERE default_code IS NOT NULL
  AND name->>'en_US' LIKE '[' || default_code || '] %';

SELECT COUNT(*) AS still_with_prefix
FROM product_template
WHERE default_code IS NOT NULL
  AND name->>'en_US' LIKE '[' || default_code || ']%';

SELECT id, default_code, name->>'en_US' AS clean_name
FROM product_template
WHERE default_code IN ('DUT300','KLAP200','SWB700','KICM050')
LIMIT 5;
