"""Open Platform Mapping → click new row's Courier dropdown → screenshot."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/tmp/kob_preview")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8069"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = ctx.new_page()

    # login
    page.goto(f"{BASE}/web/login?db=kobdb")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector("#login", state="visible", timeout=15000)
    page.fill("#login", "admin")
    page.fill("#password", "admin")
    page.locator("form.oe_login_form button[type='submit']").click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(".o_main_navbar, .o_navbar", state="visible", timeout=30000)
    page.wait_for_timeout(2500)

    # Hard reload assets
    page.evaluate("() => window.location.reload(true)")
    page.wait_for_timeout(2000)

    # Navigate to Platform Mapping
    page.goto(BASE + "/odoo/action-kob_wms_auto_batch.action_courier_platform_map")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3500)
    page.screenshot(path=str(OUT / "13_mapping_before_click.png"), full_page=True)

    # Click "New" to add a row, then click into Courier field of the new row
    new_btn = page.locator("button:has-text('New')").first
    if new_btn.count():
        new_btn.click()
        page.wait_for_timeout(800)
    # The Courier cell is empty — click it
    courier_cells = page.locator("td.o_data_cell.o_field_cell.o_required_modifier")
    print(f"courier-like cells: {courier_cells.count()}")
    # Find an empty Many2one input — click the dropdown trigger
    inputs = page.locator(".o_field_widget[name='courier_id'] input")
    n = inputs.count()
    print(f"courier_id inputs: {n}")
    if n:
        # Click the LAST one (the new row)
        inputs.nth(n - 1).click()
        page.wait_for_timeout(500)
        # Trigger the dropdown by typing nothing (just focus opens it)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(800)

    page.screenshot(path=str(OUT / "14_dropdown_open.png"), full_page=True)
    print("done")
    browser.close()
