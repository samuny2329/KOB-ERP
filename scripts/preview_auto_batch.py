"""Screenshot the auto-batch result after fixing SO/2026/02057."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/tmp/kob_preview")
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:8069"
DB = "kobdb"


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print(f"  saved {OUT / (name + '.png')}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = ctx.new_page()

    page.goto(f"{BASE}/web/login?db={DB}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector("#login", state="visible", timeout=15000)
    page.fill("#login", "admin")
    page.fill("#password", "admin")
    page.locator("form.oe_login_form button[type='submit']").click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(".o_main_navbar, .o_navbar", state="visible", timeout=30000)
    page.wait_for_timeout(2000)

    pages = [
        ("10_dispatch_rounds", "/odoo/action-kob_wms_auto_batch.action_dispatch_round"),
        ("11_courier_batches", "/odoo/action-kob_wms.action_wms_courier_batch"),
        ("12_platform_mapping", "/odoo/action-kob_wms_auto_batch.action_courier_platform_map"),
    ]
    for name, path in pages:
        print(f"[{name}]")
        page.goto(BASE + path)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3500)
        shot(page, name)

    browser.close()
print("done")
