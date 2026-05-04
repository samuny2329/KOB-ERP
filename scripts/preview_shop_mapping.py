"""Screenshot the Shop → Company mapping list."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/tmp/kob_preview")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8069"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1700, "height": 1000})
    page = ctx.new_page()
    page.goto(f"{BASE}/web/login?db=kobdb")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector("#login", state="visible", timeout=15000)
    page.fill("#login", "admin")
    page.fill("#password", "admin")
    page.locator("form.oe_login_form button[type='submit']").click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(".o_main_navbar, .o_navbar", state="visible", timeout=30000)
    page.wait_for_timeout(2500)

    page.goto(BASE + "/odoo/action-kob_marketplace_import_multi_company.action_shop_company_map")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3500)
    page.screenshot(path=str(OUT / "50_shop_company_map.png"), full_page=True)
    print("done")
    browser.close()
