# -*- coding: utf-8 -*-
"""Seed KOB warehouse employees into Odoo as hr.employee + res.users.

Run:
    docker exec -i kob-odoo-19 odoo shell -c /etc/odoo/odoo.conf -d kobdb \
        --no-http < scripts/seed_kob_employees.py

Generates:
    - hr.employee per row (full Thai + EN name, work phone, position, department)
    - res.users per row (login = first-name-en.last-name-en lowercase,
      password = nickname + last4-of-phone (e.g. Nuch2654))
    - role membership: kob_wms.group_wms_{worker,supervisor,manager,director}
      based on Job Level (EN)
    - kob.wms.user record per row with PIN = last4-of-phone (for WMS terminal)

Outputs to /tmp inside the container:
    /tmp/kob_employee_credentials.csv

We then docker cp that out to scripts/ on the host.
"""

EMPLOYEES = [
    # (first_th, last_th, first_en, last_en, nickname_en, gender,
    #  phone, position_th, position_en, level_th, level_en, section,
    #  department, role_label)
    ("ลักษ์ปัณแสง", "รุจีวณาลักษณ์", "Rukpunsang", "Rujewanalux", "Nuch", "Female", "091-964-2654",
     "เจ้าหน้าที่อาวุโสบัญชีคลังสินค้า", "Senior Warehouse Accounting Officer",
     "เจ้าหน้าที่อาวุโส", "Senior", "WH", "Warehouse and Logistics",
     "WH Account Officer / all area"),
    ("นนท์", "เล็กสมบูรณ์", "Non", "Leksomboon", "Non", "Male", "062-635-9654",
     "ผู้อำนวยการฝ่ายปฏิบัติการ", "Operations Director",
     "ผู้อำนวยการ", "Director", "SC", "Operations",
     "Director / all area"),
    ("สุวรรณี", "อุดมแก้ว", "Suwannee", "Chucho", "Wan", "Female", "063-369-6767",
     "แม่บ้าน", "Housekeeper",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Housekeeper / all area"),
    ("ศรฤทธิ์", "สมรฤทธิ์", "Sonrit", "Samonrit", "Bomb", "Male", "082-296-4552",
     "พนักงานขับรถ", "Driver",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Driver / all area"),
    ("ธนพล", "กองสิน", "Thanaphon", "Kongsin", "Pek", "Male", "062-898-2309",
     "พนักงานขับรถ", "Driver",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Driver / all area"),
    ("เมฬาภรณ์", "ทรงเอี่ยม", "Melaporn", "Songiam", "Mel", "Female", "080-983-1715",
     "พนักงานฝ่ายควบคุมคุณภาพ", "QA/QC Staff",
     "พนักงาน", "Staff", "QC", "Warehouse and Logistics",
     "QC / all area"),
    ("อาชา", "เพี้ยมูล", "Archa", "Piamoon", "Ping", "Male", "063-162-9768",
     "พนักงานคลังสินค้า", "Warehouse Officer",
     "เจ้าหน้าที่", "Officer", "WH", "Warehouse and Logistics",
     "Return / all area"),
    ("กฤษกร", "โตแก้ว", "Kritsakorn", "Tokaew", "Korn", "Male", "092-483-8704",
     "เจ้าหน้าที่คลังสินค้า", "Warehouse Officer",
     "เจ้าหน้าที่", "Officer", "WH", "Warehouse and Logistics",
     "Inventory / Offline"),
    ("ลีวินทร์", "จิตปรารภ", "Leewin", "Jitprarop", "Yong", "Female", "092-793-5928",
     "ผู้ช่วยผู้จัดการฝ่ายปฏิบัติงานคลังสินค้า", "Assistant Warehouse and Logistic Manager",
     "ผู้ช่วยผู้จัดการ", "Assistant Manager", "WH", "Warehouse and Logistics",
     "Asst.Manager / Offline"),
    ("นรินทร์", "บุญทา", "Narin", "Boontha", "Aoy", "Male", "062-546-6616",
     "เจ้าหน้าที่อาวุโสงานธุรกิจและปฏิบัติการคลังสินค้า", "Senior Admin and Operations Officer",
     "เจ้าหน้าที่อาวุโส", "Senior", "WH", "Warehouse and Logistics",
     "Admin / Online"),
    ("กฤติยา", "แสงจันทร์", "Kittiya", "Saengchan", "Nook", "Female", "094-621-4030",
     "เจ้าหน้าที่คลังสินค้า", "Warehouse Officer",
     "เจ้าหน้าที่", "Officer", "WH", "Warehouse and Logistics",
     "Pick / Online"),
    ("สังวาลย์", "บอนขาว", "Sungwan", "Bonkaw", "Pu", "Female", "099-431-1225",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Return / all area"),
    ("พชรพล", "จันทร์พันธ์", "Phacharaphon", "Chanphan", "James", "Male", "099-278-7223",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Staff / Offline"),
    ("นนทภรณ์", "คงประเสริฐ", "Nontaporn", "Kongprasert", "Bream", "Female", "080-054-6881",
     "เจ้าหน้าที่คลังสินค้า", "Warehouse Officer",
     "เจ้าหน้าที่", "Officer", "WH", "Warehouse and Logistics",
     "Officer / all area"),
    ("กัญญารัตน์", "ปีกุล", "Kanyarat", "Peegool", "Aom", "Female", "095-358-4802",
     "เจ้าหน้าที่ธุรการคลังสินค้า", "Admin Warehouse Officer",
     "เจ้าหน้าที่", "Officer", "WH", "Warehouse and Logistics",
     "Officer / Online"),
    ("พิเชษฐ์", "แต้สวัสดิ์", "Pichet", "Taesawat", "Tuk", "Male", "063-146-2335",
     "เจ้าหน้าที่อาวุโสคลังสินค้าออนไลน์", "Senior Online Warehouse Officer",
     "เจ้าหน้าที่อาวุโส", "Senior", "WH", "Warehouse and Logistics",
     "Senior / Online"),
    ("ปุณยวีร์", "เมฆะวิชัยรัตน์", "Phunyawee", "Meakavichairath", "Keaw", "Female", "082-216-1899",
     "ผู้ช่วยผู้จัดการแผนกจัดซื้อ", "Assistant Procurement Manager",
     "ผู้ช่วยผู้จัดการ", "Assistant Manager", "SC", "Supply Chain Management",
     "Asst.Manager / Purchase / all area"),
    ("วิทยา", "แสวงผล", "Wittaya", "Sawangphol", "Aof", "Male", "091-564-2276",
     "เจ้าหน้าที่อาวุโสส่วนงานนำเข้า ส่งออก และจัดซื้อ", "Senior Import/Export & Purchasing Officer",
     "เจ้าหน้าที่อาวุโส", "Senior", "SC", "Supply Chain Management",
     "Senior / IE / all area"),
    ("ชนะภัย", "โทแสง", "Chanaphai", "Thosaeng", "Ohm", "Male", "065-667-9102",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Staff / Offline"),
    ("ปัทมา", "มีภักดี", "Pattama", "Meepakdee", "Joy", "Female", "090-367-6484",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Staff / Offline"),
    ("เชาวลี", "ขุนศรี", "Chaowaree", "Khunsri", "Sine", "Female", "080-936-1696",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Pack / Online"),
    ("พนมพร", "เค้พวง", "Phnmphon", "Khephuang", "Dear", "Male", "095-364-8886",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Pick / Online"),
    ("อรณี", "พื้นชัยภูมิ", "Orranee", "Phunchaiyaphoom", "Ploy", "Female", "064-645-0903",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Pack / Online"),
    ("สิรามล", "เชื้องาม", "Siramon", "Chaungam", "Daw", "Female", "098-863-4808",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Pack / Online"),
    ("ศิวพร", "ทัพเจริญ", "Sivaporn", "Thapjaroen", "Ohm2", "Male", "064-186-4048",
     "เจ้าหน้าที่แพคเกจจิ้งคลังสินค้า", "Warehouse Packaging Officer",
     "เจ้าหน้าที่", "Officer", "WH", "Warehouse and Logistics",
     "Project Improvement / all area"),
    ("ธนัชญา", "ก๋าเร็ว", "Thanatchaya", "Ka-reo", "Aom2", "Female", "081-901-1290",
     "เจ้าหน้าที่คลังสินค้า", "Warehouse Officer",
     "เจ้าหน้าที่", "Officer", "WH", "Warehouse and Logistics",
     "Officer / Offline"),
    ("สุภาดา", "ปิ่นปัก", "Supada", "Pinpuk", "Giff", "Female", "094-063-4205",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Pick / Online"),
    ("ธิติ", "ด้วงสงต์", "Thiti", "Duangsong", "Benz", "Male", "089-788-8510",
     "Supply Chain Planner Supervisor", "Supply Chain Planner Supervisor",
     "หัวหน้างาน", "Supervisor", "SC", "Supply Chain Management",
     "Supply Chain Supervisor / all area"),
    ("หรรษา", "พื้นชัยภูมิ", "Hansa", "Punchayapoom", "King", "Female", "096-276-5154",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Pack / Online"),
    ("สุนิสา", "ศรีคนานุรักษ์", "Sunisa", "Srikhananurak", "Beam", "Female", "061-321-7167",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Pack / Online"),
    ("สุกัญญา", "จัตวาชนม์", "Sukanya", "Juttawachon", "Bee", "Female", "061-402-5835",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Officer / Offline"),
    ("ภูวดล", "พลเดช", "Phuwadon", "Pholdej", "Aun", "Male", "",
     "พนักงานคลังสินค้า", "Warehouse Staff",
     "พนักงาน", "Staff", "WH", "Warehouse and Logistics",
     "Staff / Online"),
]

# ── Role mapping ───────────────────────────────────────────────────────
LEVEL_TO_GROUP = {
    "Director":          "kob_wms.group_wms_director",
    "Assistant Manager": "kob_wms.group_wms_manager",
    "Supervisor":        "kob_wms.group_wms_supervisor",
    "Senior":            "kob_wms.group_wms_supervisor",
    "Officer":           "kob_wms.group_wms_worker",
    "Staff":             "kob_wms.group_wms_worker",
}


def _last4(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return digits[-4:] if len(digits) >= 4 else "0000"


def _sanitize(text: str) -> str:
    return "".join(c for c in (text or "").strip().lower() if c.isalnum() or c in ".")


def _login(first_en: str, last_en: str) -> str:
    """KOB login pattern: <Firstname>.<lastInitialLower>

    Example: Sivaporn Thapjaroen → "Sivaporn.t"
    """
    first = (first_en or "").strip()
    last = (last_en or "").strip()
    f_keep = "".join(c for c in first if c.isalnum())
    if f_keep:
        f_keep = f_keep[:1].upper() + f_keep[1:].lower()
    l_init = next((c.lower() for c in last if c.isalnum()), "")
    if f_keep and l_init:
        return f"{f_keep}.{l_init}"
    return f_keep or l_init or "kob.user"


def _password(nickname_en: str, phone: str) -> str:
    nick = (nickname_en or "kob").strip()
    return f"{nick}{_last4(phone)}"


# ── Idempotent seeding ─────────────────────────────────────────────────
created_users = []
created_employees = []
skipped = []

# Resolve KOB WMS groups once
def _group(xmlid):
    try:
        return env.ref(xmlid).id
    except Exception:
        return None

GROUPS_BY_LEVEL = {k: _group(v) for k, v in LEVEL_TO_GROUP.items()}
INTERNAL_USER = env.ref("base.group_user").id

# Find or create a default Department
dept_warehouse = env["hr.department"].search(
    [("name", "=", "Warehouse and Logistics")], limit=1
)
if not dept_warehouse:
    dept_warehouse = env["hr.department"].create({"name": "Warehouse and Logistics"})

dept_sc = env["hr.department"].search(
    [("name", "=", "Supply Chain Management")], limit=1
)
if not dept_sc:
    dept_sc = env["hr.department"].create({"name": "Supply Chain Management"})

dept_ops = env["hr.department"].search([("name", "=", "Operations")], limit=1)
if not dept_ops:
    dept_ops = env["hr.department"].create({"name": "Operations"})

DEPT_BY_NAME = {
    "Warehouse and Logistics": dept_warehouse.id,
    "Supply Chain Management": dept_sc.id,
    "Operations": dept_ops.id,
}

for emp in EMPLOYEES:
    (first_th, last_th, first_en, last_en, nickname_en, gender,
     phone, position_th, position_en, level_th, level_en, section,
     department, role_label) = emp

    full_name_th = f"{first_th} {last_th}".strip()
    full_name_en = f"{first_en} {last_en}".strip()
    login = _login(first_en, last_en)
    password = _password(nickname_en, phone)
    pin = _last4(phone)
    dept_id = DEPT_BY_NAME.get(department, dept_warehouse.id)
    group_xmlid = LEVEL_TO_GROUP.get(level_en, "kob_wms.group_wms_worker")
    group_id = GROUPS_BY_LEVEL.get(level_en)

    # Skip if user already exists
    existing = env["res.users"].search([("login", "=", login)], limit=1)
    if existing:
        skipped.append((login, "user exists"))
        continue

    # Create employee
    employee_vals = {
        "name": full_name_th,
        "work_phone": phone,
        "mobile_phone": phone,
        "private_phone": phone,
        "job_title": position_en,
    }
    employee = env["hr.employee"].create(employee_vals)
    # In Odoo 19 department_id and gender live on hr.version, attached
    # to the employee via current_version_id.  Set them after-the-fact.
    if employee.current_version_id:
        try:
            employee.current_version_id.write({
                "department_id": dept_id,
                "gender": (
                    "male" if gender == "Male"
                    else "female" if gender == "Female"
                    else "other"
                ),
            })
        except Exception:
            pass
    created_employees.append((full_name_th, position_en))

    # Create user
    user_vals = {
        "name": full_name_en or full_name_th,
        "login": login,
        "password": password,
        "email": f"{login}@kissofbeauty.co.th",
        "lang": "th_TH" if env["res.lang"].search(
            [("code", "=", "th_TH"), ("active", "=", True)]
        ) else "en_US",
        "tz": "Asia/Bangkok",
        "active": True,
        "group_ids": [(4, INTERNAL_USER), (4, group_id)] if group_id else [(4, INTERNAL_USER)],
    }
    user = env["res.users"].create(user_vals)

    # Link user → employee (employee.user_id)
    employee.user_id = user.id

    created_users.append((login, password, full_name_th, position_en, level_en, role_label, pin))

env.cr.commit()

# Write CSV inside the container
import csv
csv_path = "/tmp/kob_employee_credentials.csv"
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Login", "Password", "Full Name (TH)", "Position", "Job Level",
        "Role", "WMS PIN",
    ])
    for row in created_users:
        writer.writerow(row)

print(f"\n=== KOB EMPLOYEE SEED COMPLETE ===")
print(f"  Created {len(created_employees)} hr.employee records")
print(f"  Created {len(created_users)} res.users records")
print(f"  Skipped {len(skipped)} (already exist)")
print(f"  Credentials CSV: {csv_path}")
print(f"\nSample logins (first 3):")
for r in created_users[:3]:
    print(f"  login={r[0]}  password={r[1]}  ({r[2]} - {r[3]})")
