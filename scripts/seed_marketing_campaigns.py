"""Seed KOB-specific UTM sources, mediums, and campaigns for FY2026."""
env = self.env  # noqa: F821

# 1. Add KOB-specific UTM sources (e-commerce platforms + KOL channels)
SOURCES = [
    "Shopee_KissMyBody",
    "Shopee_MalissaKiss",
    "Shopee_Skinoxy",
    "Lazada_KissMyBody",
    "Lazada_MalissaKiss",
    "TikTok_KissMyBody",
    "TikTok_MalissaKiss",
    "Line_OA_KOB",
    "Influencer_BeautyKOL",
    "Influencer_NanoKOL",
    "GoogleAds_Beauty",
    "FacebookAds_Skincare",
]
for s in SOURCES:
    if not env["utm.source"].search([("name", "=", s)], limit=1):
        env["utm.source"].create({"name": s})
        print(f"  ✓ Source: {s}")

# 2. KOB-specific UTM mediums
MEDIUMS = [
    "Marketplace Ads",
    "TikTok Live",
    "Influencer Post",
    "Email Campaign",
    "SMS Blast",
    "Line Broadcast",
    "Google Ads CPC",
    "Facebook Ads CPM",
    "Banner Display",
    "Affiliate Link",
]
for m in MEDIUMS:
    if not env["utm.medium"].search([("name", "=", m)], limit=1):
        env["utm.medium"].create({"name": m})
        print(f"  ✓ Medium: {m}")

env.cr.commit()

# 3. KOB FY2026 marketing campaigns
import datetime
year = 2026
CAMPAIGNS = [
    ("Q1 2026 — KISS-MY-BODY New Year Bundle", datetime.date(year, 1, 1), datetime.date(year, 3, 31)),
    ("Q2 2026 — MALISSA Songkran Glow",        datetime.date(year, 4, 1), datetime.date(year, 6, 30)),
    ("Q3 2026 — SKINOXY Mid-Year Sale",        datetime.date(year, 7, 1), datetime.date(year, 9, 30)),
    ("Q4 2026 — KOB Holiday Gift Sets",        datetime.date(year,10, 1), datetime.date(year,12,31)),
    ("Always-On — KOL Recurring",              datetime.date(year, 1, 1), datetime.date(year,12,31)),
    ("Always-On — Shopee Live Daily",          datetime.date(year, 1, 1), datetime.date(year,12,31)),
    ("Always-On — TikTok Boost",               datetime.date(year, 1, 1), datetime.date(year,12,31)),
]
created = 0
for name, start, end in CAMPAIGNS:
    if not env["utm.campaign"].search([("name", "=", name)], limit=1):
        env["utm.campaign"].create({
            "name": name,
            "is_auto_campaign": False,
        })
        created += 1
        print(f"  ✓ Campaign: {name}")
env.cr.commit()

# Final summary
print(f"\n=== Final ===")
print(f"  UTM Sources:  {env['utm.source'].search_count([])}")
print(f"  UTM Mediums:  {env['utm.medium'].search_count([])}")
print(f"  Campaigns:    {env['utm.campaign'].search_count([])}")
