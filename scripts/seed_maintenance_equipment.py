"""Seed sample maintenance equipment + categories.

Categories: IT, Office Equipment, Vehicles, Production
Equipment: 5 sample (laptop, printer, AC, vehicle, mixer)
Plus: 2 sample preventive maintenance requests for Q2 2026.
"""
import datetime
env = self.env  # noqa: F821

# 1. Categories
CATEGORIES = ["IT Equipment", "Office Equipment", "Vehicles", "Production Machinery"]
for c in CATEGORIES:
    if not env["maintenance.equipment.category"].search([("name", "=", c)], limit=1):
        env["maintenance.equipment.category"].create({"name": c})
        print(f"  ✓ Category: {c}")

# 2. Equipment
admin = env.ref("base.user_admin", raise_if_not_found=False) or env.ref("base.user_root")
EQUIPMENT = [
    ("LAPTOP-ADMIN-001", "Admin Laptop Dell", "IT Equipment", "Dell Latitude 7420", "DLT-7420-A001", 36500.00),
    ("PRINTER-OFC-A1",   "Office Color Printer", "Office Equipment", "Brother HL-L8360", "BR-L8360-001", 18900.00),
    ("AC-OFC-MAIN",      "Main Office AC 24000 BTU", "Office Equipment", "Daikin FT24DV", "DK-FT24-001", 28500.00),
    ("VAN-DEL-001",      "Delivery Van", "Vehicles", "Toyota HiAce 2025", "TY-HC-2025-001", 1250000.00),
    ("MIX-PROD-A1",      "Cosmetic Mixer 50L", "Production Machinery", "Silverson L5MA", "SV-L5MA-001", 450000.00),
]
created = 0
cat_map = {c.name: c for c in env["maintenance.equipment.category"].search([])}
for ref, name, cat, model, serial, cost in EQUIPMENT:
    existing = env["maintenance.equipment"].search([("name", "=", name)], limit=1)
    if existing:
        continue
    env["maintenance.equipment"].create({
        "name": name,
        "category_id": cat_map[cat].id,
        "owner_user_id": admin.id,
        "technician_user_id": admin.id,
        "model": model,
        "serial_no": serial,
        "cost": cost,
        "effective_date": datetime.date(2025, 1, 1),
        "warranty_date": datetime.date(2027, 1, 1),
    })
    created += 1
    print(f"  ✓ Equipment: {name} ({cat})")

env.cr.commit()

# 3. Sample Maintenance Requests
print("\n=== Maintenance Requests ===")
mixer = env["maintenance.equipment"].search([("name", "=", "Cosmetic Mixer 50L")], limit=1)
ac = env["maintenance.equipment"].search([("name", "=", "Main Office AC 24000 BTU")], limit=1)

if mixer and not env["maintenance.request"].search(
    [("equipment_id", "=", mixer.id), ("name", "ilike", "Q2 2026")], limit=1,
):
    env["maintenance.request"].create({
        "name": "Q2 2026 Preventive — Cosmetic Mixer Lubrication",
        "equipment_id": mixer.id,
        "maintenance_type": "preventive",
        "priority": "1",
        "user_id": admin.id,
        "schedule_date": datetime.datetime(2026, 6, 15, 9, 0),
        "duration": 4.0,
        "description": (
            "Quarterly preventive: lubricate bearings, inspect seal, "
            "check torque, clean exterior. Time est: 4 hours."
        ),
    })
    print(f"  ✓ Mixer Q2 preventive scheduled (Jun 15)")

if ac and not env["maintenance.request"].search(
    [("equipment_id", "=", ac.id), ("name", "ilike", "Q2 2026")], limit=1,
):
    env["maintenance.request"].create({
        "name": "Q2 2026 Preventive — Office AC Filter Clean",
        "equipment_id": ac.id,
        "maintenance_type": "preventive",
        "priority": "0",
        "user_id": admin.id,
        "schedule_date": datetime.datetime(2026, 6, 30, 10, 0),
        "duration": 1.5,
        "description": "Filter wash, refrigerant check, drain pan clean.",
    })
    print(f"  ✓ AC Q2 preventive scheduled (Jun 30)")

env.cr.commit()
print(f"\n=== Final ===")
print(f"  Categories: {env['maintenance.equipment.category'].search_count([])}")
print(f"  Equipment:  {env['maintenance.equipment'].search_count([])}")
print(f"  Requests:   {env['maintenance.request'].search_count([])}")
