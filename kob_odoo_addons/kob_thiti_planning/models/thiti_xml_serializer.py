"""Dict tree → frePPLe input XML (UTF-8 bytes).

Schema reference: bin/frepple.xsd in the frePPLe repo. We emit the subset of
elements the C++ engine consumes for MRP/MPS planning: items, locations,
customers, suppliers, resources, operations (with flows + loads), buffers,
demands, scheduled receipts (operationplans).

Output is consumed by the engine via subprocess in Phase 5
(`thiti.solver.wrapper.run`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from lxml import etree

from odoo import api, models


def _dt(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _num(value) -> str:
    if value is None:
        return "0"
    return f"{float(value):.6g}"


class ThitiXmlSerializer(models.AbstractModel):
    _name = "thiti.xml.serializer"
    _description = "Thiti XML Serializer (dict → frePPLe XML)"

    @api.model
    def serialize(self, data: dict[str, Any],
                  plan_type: str = "1", constraint: str = "15",
                  loglevel: int = 1) -> bytes:
        nsmap = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
        root = etree.Element("plan", nsmap=nsmap)
        etree.SubElement(root, "name").text = "Thiti Planning Run"
        if data.get("current"):
            etree.SubElement(root, "current").text = _dt(data["current"])

        self._emit_calendars(root, data.get("calendars", []))
        self._emit_locations(root, data.get("locations", []))
        self._emit_customers(root, data.get("customers", []))
        self._emit_suppliers(root, data.get("suppliers", []))
        self._emit_items(root, data.get("items", []))
        self._emit_resources(root, data.get("resources", []))
        self._emit_operations(root, data.get("operations", []))
        self._emit_buffers(root, data.get("buffers", []))
        self._emit_item_suppliers(root, data.get("item_suppliers", []))
        self._emit_demands(root, data.get("demands", []))
        self._emit_operationplans(root, data.get("scheduled_receipts", []))

        xml_body = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True,
        )
        # frePPLe engine = embedded Python interpreter. <?python ?>
        # blocks must live inside <plan> to run after model load.
        # Re-emit with directives appended before closing </plan> tag.
        directive = (
            f'<?python\n'
            f'frepple.solver_mrp(plantype={plan_type}, '
            f'constraints={constraint}, loglevel={loglevel}).solve()\n'
            f'frepple.saveplan("output.xml")\n'
            f'?>\n'
        ).encode("utf-8")
        return xml_body.replace(b"</plan>", directive + b"</plan>")

    def _emit_calendars(self, root, calendars):
        if not calendars:
            return
        wrap = etree.SubElement(root, "calendars")
        for c in calendars:
            el = etree.SubElement(wrap, "calendar")
            etree.SubElement(el, "name").text = c["name"]
            etree.SubElement(el, "default").text = _num(c.get("default_value", 0))
            buckets = c.get("buckets", [])
            if buckets:
                bwrap = etree.SubElement(el, "buckets")
                for b in buckets:
                    bel = etree.SubElement(bwrap, "bucket")
                    if b.get("start_date"):
                        etree.SubElement(bel, "start").text = _dt(b["start_date"])
                    if b.get("end_date"):
                        etree.SubElement(bel, "end").text = _dt(b["end_date"])
                    etree.SubElement(bel, "value").text = _num(b.get("value", 1))
                    etree.SubElement(bel, "priority").text = str(b.get("priority", 0))

    def _emit_locations(self, root, locations):
        if not locations:
            return
        wrap = etree.SubElement(root, "locations")
        for loc in locations:
            el = etree.SubElement(wrap, "location")
            etree.SubElement(el, "name").text = loc["name"]
            if loc.get("description"):
                etree.SubElement(el, "description").text = loc["description"]
            if loc.get("owner"):
                owner_el = etree.SubElement(el, "owner")
                etree.SubElement(owner_el, "name").text = loc["owner"]

    def _emit_customers(self, root, customers):
        if not customers:
            return
        wrap = etree.SubElement(root, "customers")
        for c in customers:
            el = etree.SubElement(wrap, "customer")
            etree.SubElement(el, "name").text = c["name"]
            if c.get("description"):
                etree.SubElement(el, "description").text = c["description"]

    def _emit_suppliers(self, root, suppliers):
        if not suppliers:
            return
        wrap = etree.SubElement(root, "suppliers")
        for s in suppliers:
            el = etree.SubElement(wrap, "supplier")
            etree.SubElement(el, "name").text = s["name"]
            if s.get("description"):
                etree.SubElement(el, "description").text = s["description"]

    def _emit_items(self, root, items):
        if not items:
            return
        wrap = etree.SubElement(root, "items")
        for it in items:
            el = etree.SubElement(wrap, "item")
            etree.SubElement(el, "name").text = it["name"]
            if it.get("description"):
                etree.SubElement(el, "description").text = it["description"]
            if it.get("category"):
                etree.SubElement(el, "category").text = it["category"]
            if it.get("cost") is not None:
                etree.SubElement(el, "cost").text = _num(it["cost"])
            if it.get("price") is not None:
                etree.SubElement(el, "price").text = _num(it["price"])

    def _emit_resources(self, root, resources):
        if not resources:
            return
        wrap = etree.SubElement(root, "resources")
        for r in resources:
            el = etree.SubElement(wrap, "resource")
            etree.SubElement(el, "name").text = r["name"]
            if r.get("description"):
                etree.SubElement(el, "description").text = r["description"]
            etree.SubElement(el, "maximum").text = _num(r.get("maximum", 1))
            if r.get("cost_per_hour") is not None:
                etree.SubElement(el, "cost").text = _num(r["cost_per_hour"])
            if r.get("efficiency") is not None:
                etree.SubElement(el, "efficiency").text = _num(r["efficiency"])
            if r.get("calendar"):
                cal_el = etree.SubElement(el, "available")
                etree.SubElement(cal_el, "name").text = r["calendar"]

    def _emit_operations(self, root, operations):
        if not operations:
            return
        wrap = etree.SubElement(root, "operations")
        for op in operations:
            el = etree.SubElement(wrap, "operation")
            op_type = op.get("type", "fixed_time")
            el.set("{http://www.w3.org/2001/XMLSchema-instance}type",
                   f"operation_{op_type}")
            etree.SubElement(el, "name").text = op["name"]
            if op.get("item"):
                item_el = etree.SubElement(el, "item")
                etree.SubElement(item_el, "name").text = op["item"]
            if op.get("location"):
                loc_el = etree.SubElement(el, "location")
                etree.SubElement(loc_el, "name").text = op["location"]
            if op.get("duration_hours") is not None:
                etree.SubElement(el, "duration").text = (
                    f"PT{int((op['duration_hours'] or 0) * 3600)}S"
                )
            if op.get("size_minimum") is not None:
                etree.SubElement(el, "size_minimum").text = _num(op["size_minimum"])
            flows = op.get("flows", [])
            if flows:
                fwrap = etree.SubElement(el, "flows")
                for f in flows:
                    fel = etree.SubElement(fwrap, "flow")
                    fel.set("{http://www.w3.org/2001/XMLSchema-instance}type",
                            f"flow_{f.get('type', 'start')}")
                    item_el = etree.SubElement(fel, "item")
                    etree.SubElement(item_el, "name").text = f["item"]
                    etree.SubElement(fel, "quantity").text = _num(f.get("quantity", 1))
            loads = op.get("loads", [])
            if loads:
                lwrap = etree.SubElement(el, "loads")
                for ld in loads:
                    lel = etree.SubElement(lwrap, "load")
                    res_el = etree.SubElement(lel, "resource")
                    etree.SubElement(res_el, "name").text = ld["resource"]
                    etree.SubElement(lel, "quantity").text = _num(ld.get("quantity", 1))

    def _emit_buffers(self, root, buffers):
        if not buffers:
            return
        wrap = etree.SubElement(root, "buffers")
        for b in buffers:
            el = etree.SubElement(wrap, "buffer")
            etree.SubElement(el, "name").text = f"{b['item']} @ {b['location']}"
            item_el = etree.SubElement(el, "item")
            etree.SubElement(item_el, "name").text = b["item"]
            loc_el = etree.SubElement(el, "location")
            etree.SubElement(loc_el, "name").text = b["location"]
            etree.SubElement(el, "onhand").text = _num(b.get("onhand", 0))
            if b.get("minimum") is not None:
                etree.SubElement(el, "minimum").text = _num(b["minimum"])
            if b.get("maximum"):
                etree.SubElement(el, "maximum").text = _num(b["maximum"])

    def _emit_item_suppliers(self, root, item_suppliers):
        if not item_suppliers:
            return
        wrap = etree.SubElement(root, "itemsuppliers")
        for s in item_suppliers:
            el = etree.SubElement(wrap, "itemsupplier")
            item_el = etree.SubElement(el, "item")
            etree.SubElement(item_el, "name").text = s["item"]
            sup_el = etree.SubElement(el, "supplier")
            etree.SubElement(sup_el, "name").text = s["supplier"]
            etree.SubElement(el, "leadtime").text = (
                f"P{int(s.get('leadtime_days', 0))}D"
            )
            etree.SubElement(el, "cost").text = _num(s.get("cost", 0))
            etree.SubElement(el, "size_minimum").text = _num(s.get("size_minimum", 1))
            etree.SubElement(el, "priority").text = str(s.get("priority", 1))

    def _emit_demands(self, root, demands):
        if not demands:
            return
        wrap = etree.SubElement(root, "demands")
        for d in demands:
            el = etree.SubElement(wrap, "demand")
            etree.SubElement(el, "name").text = d["name"]
            item_el = etree.SubElement(el, "item")
            etree.SubElement(item_el, "name").text = d["item"]
            loc_el = etree.SubElement(el, "location")
            etree.SubElement(loc_el, "name").text = d["location"]
            if d.get("customer"):
                cust_el = etree.SubElement(el, "customer")
                etree.SubElement(cust_el, "name").text = d["customer"]
            etree.SubElement(el, "quantity").text = _num(d["quantity"])
            etree.SubElement(el, "due").text = _dt(d["due"])
            etree.SubElement(el, "priority").text = str(d.get("priority", 10))
            etree.SubElement(el, "status").text = d.get("status", "open")

    def _emit_operationplans(self, root, plans):
        if not plans:
            return
        wrap = etree.SubElement(root, "operationplans")
        for p in plans:
            el = etree.SubElement(wrap, "operationplan")
            el.set("{http://www.w3.org/2001/XMLSchema-instance}type",
                   "operationplan")
            etree.SubElement(el, "ordertype").text = p.get("operationplan_type", "PO")
            etree.SubElement(el, "reference").text = p.get("reference", "")
            etree.SubElement(el, "status").text = p.get("status", "confirmed")
            item_el = etree.SubElement(el, "item")
            etree.SubElement(item_el, "name").text = p["item"]
            loc_el = etree.SubElement(el, "location")
            etree.SubElement(loc_el, "name").text = p["location"]
            if p.get("supplier"):
                sup_el = etree.SubElement(el, "supplier")
                etree.SubElement(sup_el, "name").text = p["supplier"]
            etree.SubElement(el, "quantity").text = _num(p["quantity"])
            etree.SubElement(el, "end").text = _dt(p["end_date"])
