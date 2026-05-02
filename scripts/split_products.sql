-- product_template.name is jsonb in Odoo 19 (translatable field) — use ->> to text
CREATE TEMP TABLE prod_classify AS
SELECT
  pt.id AS tmpl_id,
  pt.default_code,
  CASE
    -- Packaging / RM / PM → Cosmonation (id=4)
    WHEN UPPER(pt.default_code) LIKE '031-%' THEN 4
    WHEN UPPER(pt.default_code) LIKE '030-%' THEN 4
    -- DaengGiMeoRi → Beauty Ville (id=2)
    WHEN COALESCE(pt.name->>'en_US', '') ILIKE '%DaengGiMeoRi%'
      OR COALESCE(pt.name->>'en_US', '') ILIKE '%Daeng Gi Meo Ri%'
      OR UPPER(pt.default_code) ~ '^(DGS|DGT|DJS|DJT|DUT)' THEN 2
    -- SKINOXY / KissMyBody / KOB house → KOB (id=1)
    WHEN COALESCE(pt.name->>'en_US', '') ILIKE '%Skinoxy%'
      OR COALESCE(pt.name->>'en_US', '') ILIKE '%Kiss My Body%'
      OR COALESCE(pt.name->>'en_US', '') ILIKE '%Kiss-My-Body%'
      OR COALESCE(pt.name->>'en_US', '') ILIKE '%Kiss Of Beauty%'
      OR UPPER(pt.default_code) ~ '^(SMA|SMB|SMD|STBG|STDH|SWB|OXY|KW|KMP|KLP|KTLD|KTAP|KTCC|KINN|KHKB|KTSD|KMI|KSF|KTMH|KTMM|KOB)' THEN 1
    ELSE NULL
  END AS target_company
FROM product_template pt;

SELECT target_company, COUNT(*) AS n FROM prod_classify
GROUP BY target_company ORDER BY target_company NULLS FIRST;

UPDATE product_template pt
SET company_id = pc.target_company
FROM prod_classify pc
WHERE pt.id = pc.tmpl_id
  AND pc.target_company IS NOT NULL
  AND (pt.company_id IS DISTINCT FROM pc.target_company);

SELECT
  COALESCE(c.name, 'GLOBAL_SHARED') AS company,
  COUNT(*) AS n
FROM product_template pt
LEFT JOIN res_company c ON c.id = pt.company_id
GROUP BY c.name, pt.company_id
ORDER BY pt.company_id NULLS FIRST;
