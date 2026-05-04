"""Take screenshots of kob_stage_tracker UI for review."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/tmp/kob_preview")
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:8069"
DB = "kobdb"
USER = "admin"
PASSWORD = "admin"

PO_ID = 4          # P00004
PICK_ID = 3295     # K-Off/RES/00001
TH_ID = 1          # first seeded threshold


def shot(page, name):
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  saved {path}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = ctx.new_page()

    # 1. Login
    print("[1] login")
    page.goto(f"{BASE}/web/login?db={DB}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)
    # Take a debug screenshot of the login page first
    shot(page, "00_login_page")
    page.wait_for_selector("#login", state="visible", timeout=15000)
    page.fill("#login", USER)
    page.fill("#password", PASSWORD)
    # Login form is wrapped in form.oe_login_form
    page.locator("form.oe_login_form button[type='submit']").click()
    page.wait_for_load_state("domcontentloaded")
    # Wait until Odoo top navbar is visible
    page.wait_for_selector(".o_main_navbar, .o_navbar", state="visible", timeout=30000)
    page.wait_for_timeout(2500)
    shot(page, "00_post_login")

    # 2. Stage Tracker → Transitions list
    print("[2] transitions list")
    page.goto(f"{BASE}/odoo/action-kob_stage_tracker.action_stage_transition")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3500)
    shot(page, "01_transitions_list")

    # 3. Stage Tracker → Thresholds list
    print("[3] thresholds list")
    page.goto(f"{BASE}/odoo/action-kob_stage_tracker.action_stage_threshold")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3500)
    shot(page, "02_thresholds_list")

    # 4. Threshold form (first record)
    print("[4] threshold form")
    page.goto(f"{BASE}/odoo/action-kob_stage_tracker.action_stage_threshold/{TH_ID}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3500)
    shot(page, "03_threshold_form")

    # 5. Pivot view of transitions
    print("[5] transitions pivot")
    page.goto(f"{BASE}/odoo/action-kob_stage_tracker.action_stage_transition?view_type=pivot")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    shot(page, "04_transitions_pivot")

    # 6. PO form with stat buttons
    print("[6] PO form")
    page.goto(f"{BASE}/odoo/purchase/{PO_ID}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    shot(page, "05_po_form")

    # 7. Picking form with stat buttons
    print("[7] picking form")
    page.goto(f"{BASE}/odoo/action-stock.action_picking_tree_all/{PICK_ID}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    shot(page, "06_picking_form")

    browser.close()

print("done; files in", OUT)
