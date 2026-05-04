"""Generate flat-design 256x256 app icons for KOB modules missing one.

Design system: rounded square (radius 56), vertical gradient background,
white glyph centered. Output → static/description/icon.png of each module.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path("C:/Users/kobnb/Desktop/KOB ERP/kob_odoo_addons")
SIZE = 256
RADIUS = 56


def _rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _hx(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def _gradient_bg(top_hex, bottom_hex):
    top, bot = _hx(top_hex), _hx(bottom_hex)
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        c = tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(4))
        d.line([(0, y), (SIZE, y)], fill=c)
    bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bg.paste(img, (0, 0), mask=_rounded_mask(SIZE, RADIUS))
    return bg


def _font(size):
    for name in ("arial.ttf", "ARIAL.TTF",
                 "C:/Windows/Fonts/arial.ttf",
                 "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _shadow_layer(draw_callable, blur=4, alpha=70):
    """Run draw_callable on a transparent layer, blur, return as soft shadow."""
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_callable(d, fill=(0, 0, 0, alpha))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def _arrow(d, start, end, head=14, width=8, color=(255, 255, 255, 255)):
    sx, sy = start
    ex, ey = end
    d.line([start, end], fill=color, width=width)
    ang = math.atan2(ey - sy, ex - sx)
    h1 = (ex - head * math.cos(ang - math.pi / 6),
          ey - head * math.sin(ang - math.pi / 6))
    h2 = (ex - head * math.cos(ang + math.pi / 6),
          ey - head * math.sin(ang + math.pi / 6))
    d.polygon([end, h1, h2], fill=color)


# ── 1. AI Agent ──────────────────────────────────────────────────
def make_ai_agent():
    img = _gradient_bg("#6366f1", "#8b5cf6")
    d = ImageDraw.Draw(img)
    for cx, cy, r in [(196, 64, 8), (212, 92, 5), (180, 96, 4)]:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 220))
    f = _font(120)
    text = "AI"
    bbox = d.textbbox((0, 0), text, font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (SIZE - w) // 2 - bbox[0]
    y = (SIZE - h) // 2 - bbox[1] + 4
    d.text((x + 2, y + 3), text, font=f, fill=(0, 0, 0, 60))
    d.text((x, y), text, font=f, fill="white")
    d.rectangle((76, 198, SIZE - 76, 206), fill=(255, 255, 255, 180))
    return img


# ── 2. Stage Tracker ─────────────────────────────────────────────
def make_stage_tracker():
    img = _gradient_bg("#0ea5a4", "#06756e")
    d = ImageDraw.Draw(img)
    cx, cy, R = SIZE // 2, SIZE // 2, 90
    d.ellipse((cx - R, cy - R, cx + R, cy + R),
              outline=(255, 255, 255, 230), width=8)
    d.arc((cx - R, cy - R, cx + R, cy + R),
          start=-90, end=180, fill=(255, 255, 255), width=12)
    for i, deg in enumerate((-90, 0, 90, 180)):
        a = math.radians(deg)
        ix = cx + int((R - 30) * math.cos(a))
        iy = cy + int((R - 30) * math.sin(a))
        if i < 3:
            d.ellipse((ix - 11, iy - 11, ix + 11, iy + 11), fill="white")
        else:
            d.ellipse((ix - 11, iy - 11, ix + 11, iy + 11),
                      outline="white", width=4)
    return img


# ── 3. Activity in Calendar ──────────────────────────────────────
def make_activity_calendar():
    img = _gradient_bg("#38bdf8", "#0284c7")
    d = ImageDraw.Draw(img)
    # Calendar body
    x0, y0, x1, y1 = 56, 72, 200, 208
    d.rounded_rectangle((x0, y0, x1, y1), radius=14, fill="white")
    # Header strip
    d.rounded_rectangle((x0, y0, x1, y0 + 30), radius=14, fill=(2, 132, 199, 255))
    d.rectangle((x0, y0 + 18, x1, y0 + 30), fill=(2, 132, 199, 255))
    # Hanging rings
    d.rounded_rectangle((78, 60, 90, 86), radius=4, fill=(2, 132, 199, 255))
    d.rounded_rectangle((166, 60, 178, 86), radius=4, fill=(2, 132, 199, 255))
    # Grid 4 cells (2x2)
    cell_w = (x1 - x0 - 24) // 2
    cell_h = (y1 - y0 - 30 - 24) // 2
    for r in range(2):
        for c in range(2):
            cx = x0 + 12 + c * cell_w
            cy = y0 + 30 + 12 + r * cell_h
            d.rounded_rectangle((cx, cy, cx + cell_w - 8, cy + cell_h - 8),
                                radius=6,
                                fill=(186, 230, 253, 255))
    # Highlight one cell with check
    hx, hy = x0 + 12 + cell_w, y0 + 30 + 12 + cell_h
    d.rounded_rectangle((hx, hy, hx + cell_w - 8, hy + cell_h - 8),
                        radius=6, fill=(2, 132, 199, 255))
    # Checkmark inside highlighted cell
    cxc = hx + (cell_w - 8) // 2
    cyc = hy + (cell_h - 8) // 2
    d.line([(cxc - 14, cyc + 2), (cxc - 4, cyc + 12), (cxc + 16, cyc - 10)],
           fill="white", width=6)
    return img


# ── 4. Daily Report Dispatch (MS Teams) ──────────────────────────
def make_daily_report():
    img = _gradient_bg("#8b5cf6", "#6d28d9")
    d = ImageDraw.Draw(img)
    # Document
    dx0, dy0, dx1, dy1 = 56, 60, 176, 220
    d.rounded_rectangle((dx0, dy0, dx1, dy1), radius=12, fill="white")
    # Folded corner
    d.polygon([(dx1 - 28, dy0), (dx1, dy0 + 28), (dx1 - 28, dy0 + 28)],
              fill=(216, 180, 254, 255))
    # Bar chart inside
    base = dy1 - 24
    bar_color = (109, 40, 217, 255)
    bars = [(dx0 + 16, base - 30), (dx0 + 42, base - 60), (dx0 + 68, base - 90)]
    bar_w = 18
    for bx, top in bars:
        d.rounded_rectangle((bx, top, bx + bar_w, base), radius=4,
                            fill=bar_color)
    # Two title lines
    d.rounded_rectangle((dx0 + 16, dy0 + 22, dx0 + 84, dy0 + 30),
                        radius=4, fill=(196, 181, 253, 255))
    d.rounded_rectangle((dx0 + 16, dy0 + 38, dx0 + 70, dy0 + 46),
                        radius=4, fill=(196, 181, 253, 255))
    # Paper plane / send icon (top-right)
    px, py = 200, 84
    d.polygon([(px, py), (px + 36, py + 14), (px + 12, py + 18),
               (px + 18, py + 30)], fill="white")
    d.polygon([(px + 12, py + 18), (px + 36, py + 14), (px + 18, py + 30)],
              fill=(216, 180, 254, 255))
    return img


# ── 5. DB Read-Replica ───────────────────────────────────────────
def make_db_replica():
    img = _gradient_bg("#64748b", "#1e293b")
    d = ImageDraw.Draw(img)

    def cylinder(cx, cy, w, h, fill, ring=(255, 255, 255, 255)):
        # Body
        d.rectangle((cx - w // 2, cy - h // 2 + 16,
                     cx + w // 2, cy + h // 2 - 16), fill=fill)
        # Bottom ellipse
        d.ellipse((cx - w // 2, cy + h // 2 - 32,
                   cx + w // 2, cy + h // 2), fill=fill)
        # Top ellipse
        d.ellipse((cx - w // 2, cy - h // 2,
                   cx + w // 2, cy - h // 2 + 32), fill=ring,
                  outline=ring)
        # Inner rings
        for off in (-6, 8):
            d.arc((cx - w // 2, cy + off,
                   cx + w // 2, cy + off + 24),
                  start=0, end=180, fill=(30, 41, 59, 200), width=3)

    # Primary (left, larger, brighter)
    cylinder(98, 128, 84, 140, fill=(241, 245, 249, 255))
    # Replica (right, smaller, dimmer)
    cylinder(180, 148, 70, 116, fill=(203, 213, 225, 255))
    # Sync arrow between
    _arrow(d, (140, 122), (162, 130), head=10, width=5,
           color=(255, 255, 255, 240))
    _arrow(d, (162, 150), (140, 158), head=10, width=5,
           color=(255, 255, 255, 240))
    return img


# ── 6. Polls in Discuss ──────────────────────────────────────────
def make_discuss_polls():
    img = _gradient_bg("#f43f5e", "#be123c")
    d = ImageDraw.Draw(img)
    # Speech bubble background
    bx0, by0, bx1, by1 = 40, 56, 216, 184
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=20, fill="white")
    # Tail
    d.polygon([(80, 184), (96, 184), (72, 212)], fill="white")
    # Bar chart inside (3 bars ascending)
    base = by1 - 18
    bar_color = (190, 18, 60, 255)
    for i, h in enumerate((36, 60, 84)):
        bx = bx0 + 26 + i * 50
        d.rounded_rectangle((bx, base - h, bx + 36, base), radius=6,
                            fill=bar_color)
    # Tick marks atop tallest
    cx = bx0 + 26 + 2 * 50 + 18
    d.ellipse((cx - 6, by0 + 16, cx + 6, by0 + 28), fill=(190, 18, 60, 255))
    return img


# ── 7. Finance Forecast ──────────────────────────────────────────
def make_finance_forecast():
    img = _gradient_bg("#10b981", "#047857")
    d = ImageDraw.Draw(img)
    # Chart frame baseline
    base_y = 196
    d.line([(40, base_y), (220, base_y)], fill=(255, 255, 255, 180), width=4)
    d.line([(40, 60), (40, base_y)], fill=(255, 255, 255, 180), width=4)
    # Trend polyline going up
    pts = [(56, 168), (92, 184), (124, 140), (160, 124), (200, 84)]
    d.line(pts, fill="white", width=8, joint="curve")
    # Data point dots
    for px, py in pts:
        d.ellipse((px - 7, py - 7, px + 7, py + 7), fill="white")
        d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=(4, 120, 87, 255))
    # Forecast arrow tip beyond last point
    _arrow(d, (180, 96), (216, 60), head=16, width=8,
           color=(255, 255, 255, 255))
    # "$" badge top-left
    f = _font(40)
    d.text((48, 64), "$", font=f, fill=(255, 255, 255, 220))
    return img


# ── 8. Marketplace Multi-Company ─────────────────────────────────
def make_marketplace_multi():
    img = _gradient_bg("#f59e0b", "#c2410c")
    d = ImageDraw.Draw(img)
    # Shopping bag at top
    bx0, by0, bx1, by1 = 96, 56, 160, 124
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=8, fill="white")
    # Bag handles
    d.arc((bx0 + 8, by0 - 18, bx0 + 32, by0 + 14),
          start=180, end=360, fill="white", width=5)
    d.arc((bx0 + 32, by0 - 18, bx0 + 56, by0 + 14),
          start=180, end=360, fill="white", width=5)
    # Branching arrows split into two
    _arrow(d, (128, 130), (74, 174), head=12, width=6,
           color=(255, 255, 255, 240))
    _arrow(d, (128, 130), (182, 174), head=12, width=6,
           color=(255, 255, 255, 240))
    # Two destination boxes
    for cx_box in (54, 162):
        d.rounded_rectangle((cx_box, 178, cx_box + 40, 218),
                            radius=6, fill="white")
        d.line([(cx_box, 192), (cx_box + 40, 192)],
               fill=(194, 65, 12, 255), width=3)
        d.rectangle((cx_box + 16, 178, cx_box + 24, 192),
                    fill=(194, 65, 12, 255))
    return img


# ── 9. Sales Stock Lite ──────────────────────────────────────────
def make_sales_stock_lite():
    img = _gradient_bg("#84cc16", "#4d7c0f")
    d = ImageDraw.Draw(img)
    # Cardboard box (isometric-ish)
    bx0, by0, bx1, by1 = 56, 96, 168, 208
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=8,
                        fill=(254, 252, 232, 255))
    # Box flap top
    d.polygon([(bx0, by0), (bx1, by0), ((bx0 + bx1) // 2, by0 - 26)],
              fill=(254, 240, 138, 255), outline=(77, 124, 15, 255))
    # Tape
    d.line([((bx0 + bx1) // 2, by0), ((bx0 + bx1) // 2, by1)],
           fill=(77, 124, 15, 255), width=5)
    d.rectangle((bx0 + 24, by0 + 36, bx1 - 24, by0 + 50),
                fill=(217, 119, 6, 200))
    # Price tag (top-right corner)
    tx0, ty0 = 156, 56
    d.polygon([(tx0, ty0), (tx0 + 56, ty0), (tx0 + 76, ty0 + 28),
               (tx0 + 56, ty0 + 56), (tx0, ty0 + 56)], fill="white")
    # Tag hole
    d.ellipse((tx0 + 56, ty0 + 20, tx0 + 72, ty0 + 36),
              fill=(132, 204, 22, 255))
    # "$"
    f = _font(28)
    d.text((tx0 + 14, ty0 + 14), "$", font=f, fill=(77, 124, 15, 255))
    return img


# ── 10. Timesheet Timer ──────────────────────────────────────────
def make_timesheet_navbar():
    img = _gradient_bg("#ec4899", "#be185d")
    d = ImageDraw.Draw(img)
    cx, cy, R = SIZE // 2, 142, 78
    # Top button
    d.rounded_rectangle((cx - 14, cy - R - 22, cx + 14, cy - R - 6),
                        radius=4, fill="white")
    # Side button
    d.rounded_rectangle((cx + R - 4, cy - R + 4, cx + R + 12, cy - R + 18),
                        radius=4, fill="white")
    # Watch face outline
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill="white")
    # Inner face
    d.ellipse((cx - R + 8, cy - R + 8, cx + R - 8, cy + R - 8),
              fill=(252, 231, 243, 255))
    # Tick marks at 12, 3, 6, 9
    for deg in (-90, 0, 90, 180):
        a = math.radians(deg)
        x1 = cx + int((R - 16) * math.cos(a))
        y1 = cy + int((R - 16) * math.sin(a))
        x2 = cx + int((R - 24) * math.cos(a))
        y2 = cy + int((R - 24) * math.sin(a))
        d.line([(x1, y1), (x2, y2)], fill=(190, 24, 93, 255), width=4)
    # Hands (running)
    d.line([(cx, cy), (cx + 28, cy - 36)], fill=(190, 24, 93, 255), width=6)
    d.line([(cx, cy), (cx, cy - 50)], fill=(190, 24, 93, 255), width=4)
    d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=(190, 24, 93, 255))
    # Caption strip below (suggesting navbar position)
    d.rounded_rectangle((52, 232, SIZE - 52, 244), radius=6,
                        fill=(255, 255, 255, 220))
    return img


# ── 11. WMS Auto Dispatch Batch ──────────────────────────────────
def make_wms_auto_batch():
    img = _gradient_bg("#3b82f6", "#1e3a8a")
    d = ImageDraw.Draw(img)

    def small_box(x, y, w=58, h=44, fill=(255, 255, 255, 255)):
        d.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=fill)
        d.line([(x, y + 14), (x + w, y + 14)],
               fill=(30, 58, 138, 255), width=3)
        d.rectangle((x + (w // 2) - 4, y, x + (w // 2) + 4, y + 14),
                    fill=(30, 58, 138, 255))

    # Stack: bottom (centered), middle two side-by-side, top one
    small_box(99, 162)              # bottom center
    small_box(64, 116)               # middle left
    small_box(134, 116)              # middle right
    small_box(99, 70)                # top center
    # Circular auto-arrow around stack
    cx, cy, R = SIZE // 2, 138, 108
    d.arc((cx - R, cy - R, cx + R, cy + R),
          start=-30, end=210, fill=(255, 255, 255, 230), width=8)
    # Arrowhead at the end of arc
    end_ang = math.radians(210)
    ex = cx + int(R * math.cos(end_ang))
    ey = cy + int(R * math.sin(end_ang))
    # Tangent direction
    tang = end_ang + math.pi / 2
    head = 16
    h1 = (ex - head * math.cos(tang - math.pi / 6),
          ey - head * math.sin(tang - math.pi / 6))
    h2 = (ex - head * math.cos(tang + math.pi / 6),
          ey - head * math.sin(tang + math.pi / 6))
    d.polygon([(ex, ey), h1, h2], fill=(255, 255, 255, 230))
    return img


# ─────────────────────────────────────────────────────────────────
def write_icon(module, builder):
    target = ROOT / module / "static" / "description"
    target.mkdir(parents=True, exist_ok=True)
    out = target / "icon.png"
    img = builder()
    img.save(out, "PNG", optimize=True)
    print(f"  [OK] {module}/static/description/icon.png "
          f"({out.stat().st_size} bytes)")


BUILDERS = [
    ("kob_ai_agent", make_ai_agent),
    ("kob_stage_tracker", make_stage_tracker),
    ("kob_activity_calendar", make_activity_calendar),
    ("kob_daily_report_extras", make_daily_report),
    ("kob_db_replica", make_db_replica),
    ("kob_discuss_polls", make_discuss_polls),
    ("kob_finance_forecast", make_finance_forecast),
    ("kob_marketplace_import_multi_company", make_marketplace_multi),
    ("kob_sales_stock_lite", make_sales_stock_lite),
    ("kob_timesheet_navbar", make_timesheet_navbar),
    ("kob_wms_auto_batch", make_wms_auto_batch),
]


if __name__ == "__main__":
    print("Generating KOB module icons (256x256 PNG)...")
    for name, fn in BUILDERS:
        write_icon(name, fn)
    print("Done.")
