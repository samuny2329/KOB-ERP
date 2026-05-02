-- Apply real product names captured from UAT stock-report (134 SKUs)
-- Source: kissgroupdatacenter.com/odoo/stock-report → product.product

CREATE TEMP TABLE uat_names (sku TEXT, real_name TEXT);

INSERT INTO uat_names (sku, real_name) VALUES
('AVH290','MALISSA-KISS Soothing Gel 290 g'),
('AVS230','MALISSA-KISS Soothing Gel 230 g'),
('CMC025','COSMOOD Sheet Mask 25 g'),
('DCC003-SET','DGMR SET Brush & Cotton Bag Box'),
('DDP200','DAENG-GI-MEO-RI Intensive Nourishing Pack 200 ml'),
('DDS400','DAENG-GI-MEO-RI Shampoo 400 ml'),
('DDT400','DAENG-GI-MEO-RI Treatment 400 ml'),
('DGS007','DAENG-GI-MEO-RI Shampoo 7 ml'),
('DGS400','DAENG-GI-MEO-RI Shampoo 400 ml'),
('DGT050','DAENG-GI-MEO-RI Treatment 50 ml'),
('DGT400','DAENG-GI-MEO-RI Treatment 400 ml'),
('DJS050','DAENG-GI-MEO-RI Shampoo 50 ml'),
('DJS300','DAENG-GI-MEO-RI Shampoo 300 ml'),
('DJS500','DAENG-GI-MEO-RI Shampoo 500 ml'),
('DJT050','DAENG-GI-MEO-RI Treatment 50 ml'),
('DJT100','DAENG-GI-MEO-RI Jingi Anti-Hair Loss Scalp Tonic 100 ml'),
('DJT300','DAENG-GI-MEO-RI Treatment 300 ml'),
('DJT500','DAENG-GI-MEO-RI Treatment 500 ml'),
('DSB001-GWP','DAENG-GI-MEO-RI Scalp hair brush'),
('DSS050','DAENG-GI-MEO-RI Shampoo 50 ml'),
('DSS300','DAENG-GI-MEO-RI Shampoo 300 ml'),
('DST050','DAENG-GI-MEO-RI Treatment 50 ml'),
('DST300','DAENG-GI-MEO-RI Treatment 300 ml'),
('DUS300','DAENG-GI-MEO-RI Shampoo 300 ml'),
('EAS200','EGG-PLANET Shampoo 200 ml'),
('EAT200','EGG-PLANET Treatment 200 ml'),
('GWP-KBB001','KISS MY BODY Bath Ball'),
('GWP-MIRI-HAIR-BAND','MIRIMIRI Satin Hair Band'),
('GWP-MIRI-MINI-HB001','MIRIMIRI New Bristle Hair Blush (หวีขนหมูป่า mini)'),
('KCCU011','KISS-MY-LIFE Car Perfume 11 ml'),
('KCOL011','KISS-MY-LIFE Car Perfume 11 ml'),
('KICM050','KISS-MY-BODY Eau De Parfum Intense 50 ml'),
('KINN050','KISS-MY-BODY Eau De Parfum Intense 50 ml'),
('KLAP200','KISS-MY-BODY Bright & Shine Perfume Lotion 200 g'),
('KLC226','KISS-MY-BODY Bright & Shine Perfume Lotion 226 g'),
('KLCC200','KISS-MY-BODY Bright & Shine Perfume Lotion 200 g'),
('KLD200','KISS-MY-BODY Bright & Shine Perfume Lotion SPF30 PA+++ 200 g'),
('KLH200','KISS-MY-BODY Bright & Shine Perfume Lotion SPF30 PA+++ 200 g'),
('KLL226','KISS-MY-BODY Bright & Shine Perfume Lotion 226 g'),
('KLMH180','KISS-MY-BODY Tone Up Perfume Lotion 180 g'),
('KLMM180','KISS-MY-BODY Tone Up Perfume Lotion 180 g'),
('KLP226','KISS-MY-BODY Bright & Shine Perfume Lotion 226 g'),
('KLS226','KISS-MY-BODY Bright & Shine Perfume Lotion 226 g'),
('KLSD200','KISS-MY-BODY Bright & Shine Perfume Lotion 200 g'),
('KLT200','KISS-MY-BODY Bright & Shine Perfume Lotion 200 g'),
('KMC088','KISS-MY-BODY Perfume Mist 88 ml'),
('KMD088','KISS-MY-BODY Perfume Mist 88 ml'),
('KME088','KISS-MY-BODY Perfume Mist 88 ml'),
('KMF088','KISS-MY-BODY Perfume Mist 88 ml'),
('KMH088','KISS-MY-BODY Perfume Mist 88 ml'),
('KML080','KISS-MY-BODY Eau De Toilette 80 ml'),
('KML088','KISS-MY-BODY Perfume Mist 88 ml'),
('KMP088','KISS-MY-BODY Perfume Mist 88 ml'),
('KMS080','KISS-MY-BODY Eau De Toilette 80 ml'),
('KMS088','KISS-MY-BODY Perfume Mist 88 ml'),
('KMT088','KISS-MY-BODY Perfume Mist 88 ml'),
('KMV088','KISS-MY-BODY Perfume Mist 88 ml'),
('KMW088','KISS-MY-BODY Perfume Mist 88 ml'),
('KPCL050','KISS-MY-BODY Eau De Parfum 50 ml'),
('KPDD050','KISS-MY-BODY Eau De Parfum 50 ml'),
('KPGK050','KISS-MY-BODY Eau De Parfum 50 ml'),
('KPSS050','KISS-MY-BODY Eau De Parfum 50 ml'),
('KPVD050','KISS-MY-BODY Eau De Parfum 50 ml'),
('KPWF050','KISS-MY-BODY Eau De Parfum 50 ml'),
('KSCP180','KISS-MY-BODY Sun Protection Perfume Serum SPF50 PA++++ 180 g'),
('KSSM180','KISS-MY-BODY Sun Protection Perfume Serum SPF50 PA++++ 180 g'),
('KTAP088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTBG088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTBM088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTBR088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTCA088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTCC088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTCP088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTFL088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTLD088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTLM088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTPR088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KTSM088','KISS-MY-BODY Eau De Toilette 88 ml'),
('KUBB045','KISS-MY-BODY Underarm Dry Serum 45 g'),
('KUSS045','KISS-MY-BODY Underarm Dry Serum 45 g'),
('KWAP380','KISS-MY-BODY Perfume Shower Gel 380 ml'),
('KWC380','KISS-MY-BODY Perfume Shower Gel 380 ml'),
('KWCC380','KISS-MY-BODY Perfume Shower Gel 380 ml'),
('KWE380','KISS-MY-BODY Perfume Shower Gel 380 ml'),
('KWF380','KISS-MY-BODY Perfume Shower Gel 380 ml'),
('KWP380','KISS-MY-BODY Perfume Shower Gel 380 ml'),
('KWS380','KISS-MY-BODY Perfume Shower Gel 380 ml'),
('LMS500','LOOK-AT-HAIR-LOSS Deep Cooling Shampoo 500 ml'),
('LMT500','LOOK-AT-HAIR-LOSS Treatment 500 ml'),
('SAVC050','SKINOXY Soothing Gel 50g'),
('SAVC230','SKINOXY Soothing Gel 230 g'),
('SAVH230','SKINOXY Soothing Gel 230 g'),
('SBA275','SKINOXY Body Serum 275 g'),
('SBB030','SKINOXY Body Serum 30 g'),
('SBB275','SKINOXY Body Serum 275 g'),
('SBPR275','SKINOXY Body Serum 275 g'),
('SBPS030','SKINOXY Pro Sun Protection Body Lotion SPF50+ PA++++ 30 g'),
('SBPS180','SKINOXY Pro Sun Protection Body Lotion SPF50+ PA++++ 180 g'),
('SBPU275','SKINOXY Body Serum 275 g'),
('SBR030','SKINOXY Body Serum 30 g'),
('SBR275','SKINOXY Body Serum 275 g'),
('SCPH220','SKINOXY Pro Cleanser 220 ml'),
('SCPS220','SKINOXY Pro Cleanser 220 ml'),
('SHGG030','SKINOXY Hydrogel Mask 30g'),
('SHLF030','SKINOXY Hydrogel Mask 30g'),
('SMA025','SKINOXY Mask'),
('SMB025','SKINOXY Mask'),
('SMBS025','SKINOXY Mask'),
('SMBS025-CL','SKINOXY Mask [CL]'),
('SMD025','SKINOXY Mask'),
('SMGG022','SKINOXY Mask'),
('SMHB025','SKINOXY Mask'),
('SMLR025','SKINOXY Mask'),
('SMSR025','SKINOXY Mask'),
('SSPC010','SKINOXY Booster Serum 10 ml'),
('SSPC030','SKINOXY Pro Booster Serum 30 ml'),
('SSPH030','SKINOXY Pro Booster Serum 30 ml'),
('SSPR010','SKINOXY Booster Serum 10 ml'),
('SSPR030','SKINOXY Pro Booster Serum 30 ml'),
('STBG080','SKINOXY Toner Pad 150 ml (80 Sheets)'),
('STBG080-REFILL','SKINOXY Refill Toner Pad 150 ml (80 Sheets)'),
('STDH010','Skinoxy Toner Pad 10 Pad'),
('STDH080','SKINOXY Toner Pad 150 ml (80 Sheets)'),
('STDH080-REFILL','SKINOXY Refill Toner Pad 150 ml (80 Sheets)'),
('SWB700','SKINOXY Body Wash 700ml'),
('SWH700','SKINOXY Body Wash 700ml'),
('TLL040','2SOME1 Whitening Perfume Body Lotion 40 g'),
('TPAB030','2SOME1 Perfume 30 ml'),
('TPBS030','2SOME1 Perfume 30 ml'),
('TPDQ030','2SOME1 Perfume 30 ml'),
('TPHQ030','2SOME1 Perfume 30 ml'),
('TPSB030','2SOME1 Perfume 30 ml'),
('TSAQ030','2SOME1 Whitening Booster Serum Aura Queen 30 g'),
('TSSA010','2SOME1 Perfume Sweet Angel 10 ml');

-- 1) Update product_template.name
UPDATE product_template pt
SET name = jsonb_set(pt.name, '{en_US}', to_jsonb(u.real_name))
FROM uat_names u
WHERE pt.default_code = u.sku;

-- 2) Cascade to wms.sales.order.line.product_name → '[SKU] real_name'
UPDATE wms_sales_order_line l
SET product_name = '[' || pp.default_code || '] ' || u.real_name
FROM product_product pp
JOIN uat_names u ON u.sku = pp.default_code
WHERE l.product_id = pp.id;

-- 3) Cascade to sale.order.line.name (jsonb) — keep [SKU] prefix
UPDATE sale_order_line sol
SET name = jsonb_set(
    COALESCE(sol.name, '{}'::jsonb), '{en_US}',
    to_jsonb('[' || pp.default_code || '] ' || u.real_name)
)
FROM product_product pp
JOIN uat_names u ON u.sku = pp.default_code
WHERE sol.product_id = pp.id;

-- Report
SELECT 'updated_templates' AS m, COUNT(*) FROM product_template pt
JOIN uat_names u ON u.sku = pt.default_code;

SELECT pt.default_code, pt.name->>'en_US' AS name
FROM product_template pt
JOIN uat_names u ON u.sku = pt.default_code
WHERE pt.default_code IN ('KLAP200','KMP088','KWS380','SWB700','STDH010','DJT100')
ORDER BY pt.default_code;
