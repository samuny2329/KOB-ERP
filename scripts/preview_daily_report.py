"""Screenshot the Daily Report form view."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/tmp/kob_preview")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8069"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1100})
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

    # List view
    page.goto(BASE + "/odoo/action-kob_wms.action_wms_daily_report")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3500)
    page.screenshot(path=str(OUT / "20_daily_report_list.png"), full_page=True)

    # Form view of the most recent record (id=6)
    page.goto(BASE + "/odoo/action-kob_wms.action_wms_daily_report/6")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3500)
    page.screenshot(path=str(OUT / "21_daily_report_form.png"), full_page=True)
    print("done")
    browser.close()
