# -*- coding: utf-8 -*-
"""Create kob.wms.user (WMS terminal profile) for every internal user.

Uses the data already seeded into hr.employee + res.users by
seed_kob_employees.py:
  - matches by user.email (firstname.lastname@kissofbeauty.local)
  - WMS username = login (firstname.lastname)
  - PIN = last 4 digits of res.users.partner_id.phone (or fallback 1234)
  - role mapped from the user's WMS group:
      group_wms_director  → admin
      group_wms_manager   → supervisor
      group_wms_supervisor→ supervisor
      group_wms_worker    → picker (default; we refine below by role label)

Run:
    docker exec -i kob-odoo-19 odoo shell --config=/etc/odoo/odoo.conf \
        -d kobdb --no-http < scripts/seed_kob_wms_profiles.py
"""

# ── Lookup tables ──────────────────────────────────────────────────────
# Same employee dataset (subset of fields needed here) — keyed by login.
# Lets us pick the right WMS role + PIN for each profile.
ROLE_BY_LABEL_KEYWORD = [
    ("director",   "admin"),
    ("asst.manager", "supervisor"),
    ("supervisor", "supervisor"),
    ("senior",     "supervisor"),
    ("admin",      "supervisor"),
    ("pick",       "picker"),
    ("pack",       "packer"),
    ("outbound",   "outbound"),
    ("dispatch",   "outbound"),
    ("driver",     "outbound"),
    ("return",     "picker"),
    ("inventory",  "picker"),
    ("qc",         "supervisor"),
    ("housekeeper","viewer"),
    ("project",    "supervisor"),
    ("officer",    "picker"),
    ("staff",      "picker"),
]

EMP_LABELS = {
    "rukpunsang.rujewanalux":  "WH Account Officer / all area",
    "non.leksomboon":           "Director / all area",
    "suwannee.chucho":          "Housekeeper / all area",
    "sonrit.samonrit":          "Driver / all area",
    "thanaphon.kongsin":        "Driver / all area",
    "melaporn.songiam":         "QC / all area",
    "archa.piamoon":            "Return / all area",
    "kritsakorn.tokaew":        "Inventory / Offline",
    "leewin.jitprarop":         "Asst.Manager / Offline",
    "narin.boontha":            "Admin / Online",
    "kittiya.saengchan":        "Pick / Online",
    "sungwan.bonkaw":           "Return / all area",
    "phacharaphon.chanphan":    "Staff / Offline",
    "nontaporn.kongprasert":    "Officer / all area",
    "kanyarat.peegool":         "Officer / Online",
    "pichet.taesawat":          "Senior / Online",
    "phunyawee.meakavichairath":"Asst.Manager / Purchase / all area",
    "wittaya.sawangphol":       "Senior / IE / all area",
    "chanaphai.thosaeng":       "Staff / Offline",
    "pattama.meepakdee":        "Staff / Offline",
    "chaowaree.khunsri":        "Pack / Online",
    "phnmphon.khephuang":       "Pick / Online",
    "orranee.phunchaiyaphoom":  "Pack / Online",
    "siramon.chaungam":         "Pack / Online",
    "sivaporn.thapjaroen":      "Project Improvement / all area",
    "thanatchaya.kareo":        "Officer / Offline",
    "supada.pinpuk":            "Pick / Online",
    "thiti.duangsong":          "Supply Chain Supervisor / all area",
    "hansa.punchayapoom":       "Pack / Online",
    "sunisa.srikhananurak":     "Pack / Online",
    "sukanya.juttawachon":      "Officer / Offline",
    "phuwadon.pholdej":         "Staff / Online",
}


def _resolve_role(label):
    label_lower = (label or "").lower()
    for keyword, role in ROLE_BY_LABEL_KEYWORD:
        if keyword in label_lower:
            return role
    return "viewer"


# ── Seed ───────────────────────────────────────────────────────────────
created = 0
updated = 0

for login, label in EMP_LABELS.items():
    user = env["res.users"].search([("login", "=", login)], limit=1)
    if not user:
        continue
    employee = env["hr.employee"].search(
        [("user_id", "=", user.id)], limit=1,
    )
    phone = (user.partner_id.phone
             or (employee and (employee.work_phone or employee.mobile_phone)) or "")
    digits = "".join(c for c in str(phone) if c.isdigit())
    pin = digits[-4:] if len(digits) >= 4 else "1234"
    role = _resolve_role(label)

    existing = env["kob.wms.user"].search(
        [("username", "=", login)], limit=1,
    )
    vals = {
        "name": user.name,
        "position": (employee and employee.job_title) or label,
        "username": login,
        "role": role,
        "is_active": True,
        "res_user_id": user.id,
        "pin": pin,        # plain text — model authenticate_pin handles it
    }
    if existing:
        existing.write(vals)
        updated += 1
    else:
        env["kob.wms.user"].create(vals)
        created += 1

env.cr.commit()
print(f"\n=== KOB WMS PROFILE SEED ===")
print(f"  Created: {created}")
print(f"  Updated: {updated}")
print(f"  Total:   {created + updated}")
