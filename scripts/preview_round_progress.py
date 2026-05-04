"""Screenshot dispatch round form showing new progress fields + breakdown."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/tmp/kob_preview")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8069"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1800, "height": 1300})
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

    # Open the round form (we know id=5 from earlier — DR/20260504/005)
    page.goto(BASE + "/odoo/action-kob_wms_auto_batch.action_dispatch_round/5")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(4000)
    # Hide chatter
    page.evaluate("""() => {
      document.querySelectorAll('.o-mail-Chatter').forEach(e => e.style.display='none');
    }""")
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "60_round_with_progress.png"), full_page=True)

    # Click on "Per-platform breakdown" tab
    tabs = page.locator("a.nav-link, .o_notebook_headers a").filter(has_text="breakdown")
    if tabs.count():
        tabs.first.click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "61_round_breakdown_tab.png"), full_page=True)
    print("done")
    browser.close()
