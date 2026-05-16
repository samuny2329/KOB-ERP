"""Generate Thiti Planning brand logo.

Output: 140x140 PNG (Odoo app icon size) + 512x512 PNG (high-res).
Design: Stylized planet+orbit (planning = scheduled orbits in time/space)
with bold T monogram, KOB blue background + frePPLe orange accent ring.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

KOB_BLUE = (0, 43, 92, 255)      # #002B5C
FRPP_ORANGE = (245, 166, 35, 255) # #F5A623
KOB_RED = (200, 16, 46, 255)     # #C8102E
WHITE = (255, 255, 255, 255)
BG_GRAD_DARK = (0, 25, 55, 255)   # darker blue


def render_logo(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    cx, cy = size / 2, size / 2

    # Outer circular plate — KOB blue with subtle radial shading via
    # 4 concentric rings of increasing alpha.
    for i, alpha in enumerate([255, 240, 220, 200]):
        radius = size / 2 - i * (size * 0.005)
        color = KOB_BLUE[:3] + (alpha,)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=color,
        )

    # Orbital ring — orange, tilted ellipse (planning = orbit of operations)
    orbit_w = size * 0.82
    orbit_h = size * 0.32
    orbit_thickness = max(int(size * 0.025), 3)
    bbox = [cx - orbit_w / 2, cy - orbit_h / 2,
            cx + orbit_w / 2, cy + orbit_h / 2]
    draw.ellipse(bbox, outline=FRPP_ORANGE, width=orbit_thickness)

    # Second smaller orbit, rotated mentally (vertical) — red accent
    orbit2_w = size * 0.30
    orbit2_h = size * 0.78
    bbox2 = [cx - orbit2_w / 2, cy - orbit2_h / 2,
             cx + orbit2_w / 2, cy + orbit2_h / 2]
    draw.ellipse(bbox2, outline=KOB_RED[:3] + (180,), width=max(int(size * 0.015), 2))

    # Central planet — white disc
    planet_r = size * 0.18
    draw.ellipse(
        [cx - planet_r, cy - planet_r, cx + planet_r, cy + planet_r],
        fill=WHITE,
    )

    # "T" monogram inside planet
    font_size = int(size * 0.22)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    text = "T"
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    draw.text(
        (cx - tw / 2 - tb[0], cy - th / 2 - tb[1]),
        text,
        font=font,
        fill=KOB_BLUE,
    )

    # Dots on the orbital ring — scheduled events / operations
    import math
    for angle_deg in (45, 135, 225, 315):
        a = math.radians(angle_deg)
        dx = cx + (orbit_w / 2) * math.cos(a)
        dy = cy + (orbit_h / 2) * math.sin(a)
        dot_r = size * 0.035
        draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r],
                     fill=FRPP_ORANGE)

    return img


def main() -> None:
    target_dir = Path(__file__).resolve().parent.parent / \
        "kob_odoo_addons" / "kob_thiti_planning" / "static" / "description"
    target_dir.mkdir(parents=True, exist_ok=True)

    for size, suffix in [(140, ""), (512, "_512"), (1024, "_1024")]:
        img = render_logo(size)
        out = target_dir / f"icon{suffix}.png"
        img.save(out, "PNG", optimize=True)
        print(f"Wrote {out} ({size}x{size})")


if __name__ == "__main__":
    main()
