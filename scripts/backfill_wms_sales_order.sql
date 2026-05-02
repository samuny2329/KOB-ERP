-- Backfill wms.sales.order linkages from sale.order + utm.source
-- Fixes: sale_order_id NULL, platform="manual", ref=picking name
--        (should be marketplace order_sn)

-- 1) Find sale_order_id from picking_id and link
UPDATE wms_sales_order wso
SET sale_order_id = sp.sale_id
FROM stock_picking sp
WHERE wso.picking_id = sp.id
  AND wso.sale_order_id IS NULL
  AND sp.sale_id IS NOT NULL;

-- 2) Derive platform from utm.source.name
UPDATE wms_sales_order wso
SET platform = CASE
    WHEN ut.name ILIKE 'shopee%' THEN 'shopee'
    WHEN ut.name ILIKE 'lazada%' THEN 'lazada'
    WHEN ut.name ILIKE 'tiktok%' THEN 'tiktok'
    WHEN ut.name ILIKE 'pos%'    THEN 'pos'
    WHEN ut.name ILIKE 'odoo%'   THEN 'odoo'
    ELSE wso.platform
END
FROM sale_order so
LEFT JOIN utm_source ut ON ut.id = so.source_id
WHERE wso.sale_order_id = so.id
  AND ut.name IS NOT NULL;

-- 3) Set ref = marketplace order_sn (sale_order.client_order_ref)
UPDATE wms_sales_order wso
SET ref = so.client_order_ref
FROM sale_order so
WHERE wso.sale_order_id = so.id
  AND so.client_order_ref IS NOT NULL
  AND wso.ref != so.client_order_ref;

-- 4) Sync customer text from sale_order.partner.name (in case stale)
UPDATE wms_sales_order wso
SET customer = COALESCE(so.partner_id::text || '', wso.customer)
FROM sale_order so
WHERE wso.sale_order_id = so.id
  AND wso.customer IS NULL OR wso.customer = '';

-- Report
SELECT platform, COUNT(*) FROM wms_sales_order GROUP BY platform ORDER BY platform;

SELECT
  COUNT(*) FILTER (WHERE sale_order_id IS NOT NULL) AS linked,
  COUNT(*) FILTER (WHERE sale_order_id IS NULL)     AS unlinked,
  COUNT(*) FILTER (WHERE platform != 'manual')      AS platform_set,
  COUNT(*)                                          AS total
FROM wms_sales_order;
