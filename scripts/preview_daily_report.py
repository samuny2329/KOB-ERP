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
    page.screenshot(path=str(OUT / "40_wms_daily_list.png"), full_page=True)

    # Form view of KISS report (id=9 — has data) — bigger viewport for legibility
    ctx2 = browser.new_context(viewport={"width": 1800, "height": 1400})
    page2 = ctx2.new_page()
    page2.goto(f"{BASE}/web/login?db=kobdb")
    page2.wait_for_load_state("domcontentloaded")
    page2.wait_for_selector("#login", state="visible", timeout=15000)
    page2.fill("#login", "admin")
    page2.fill("#password", "admin")
    page2.locator("form.oe_login_form button[type='submit']").click()
    page2.wait_for_load_state("domcontentloaded")
    page2.wait_for_selector(".o_main_navbar, .o_navbar", state="visible", timeout=30000)
    page2.wait_for_timeout(2000)
    page2.goto(BASE + "/odoo/action-kob_wms.action_wms_daily_report/9")
    page2.wait_for_load_state("domcontentloaded")
    page2.wait_for_timeout(4500)
    # Hide chatter to focus on the body
    page2.evaluate("""() => {
      const aside = document.querySelector('.o-mail-Chatter, aside.o_form_view, .o-mail-ChatterContainer');
      if (aside) aside.style.display = 'none';
      // Expand/scroll the form sheet
      const sheet = document.querySelector('.o_form_sheet_bg');
      if (sheet) sheet.scrollIntoView({block:'start'});
    }""")
    page2.wait_for_timeout(800)
    page2.screenshot(path=str(OUT / "41_wms_daily_form_kiss.png"), full_page=True)
    page2.close()
    ctx2.close()

    # Render body_html in a clean iframe-free page so the card style is
    # easy to inspect
    body_html = page.evaluate("""() => {
        const el = document.querySelector('.note-editable, .o_field_html, [name=\"body_html\"]');
        return el ? el.innerHTML : null;
    }""")
    if body_html:
        clean_html = (
            "<!doctype html><html><head>"
            f'<link rel="stylesheet" href="{BASE}/web/assets/web.assets_backend.bundle.css"/>'
            '<meta charset="utf-8"/><title>WMS Daily preview</title>'
            "</head>"
            '<body style="margin:24px;background:#f9f9f9">'
            f"{body_html}"
            "</body></html>"
        )
        with open("C:/tmp/kob_preview/42_wms_daily_card.html", "w", encoding="utf-8") as f:
            f.write(clean_html)
        # Open it
        page.goto("file:///C:/tmp/kob_preview/42_wms_daily_card.html")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT / "42_wms_daily_card_clean.png"), full_page=True)
    print("done")
    browser.close()
