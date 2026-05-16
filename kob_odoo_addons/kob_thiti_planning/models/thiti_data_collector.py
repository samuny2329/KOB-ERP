"""Odoo native models → frePPLe input dict tree.

Maps live Odoo data (product.product, mrp.bom, mrp.workcenter, stock.quant,
sale.order.line, purchase.order.line, product.supplierinfo, res.company) into
a dict structure consumable by `thiti.xml.serializer` for engine input.

This collector is the ONLY translation layer between Odoo and the frePPLe
engine — once Phase 5 wires the solver, plan output flows back into the
`thiti.plan.*` storage models for native Odoo display.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from odoo import api, fields, models


class ThitiDataCollector(models.AbstractModel):
    _name = "thiti.data.collector"
    _description = "Thiti Data Collector (Odoo → frePPLe input)"

    @api.model
    def collect(self, run) -> dict[str, Any]:
        horizon = run.plan_horizon_days or 90
        current = run.plan_currentdate or fields.Datetime.now()
        horizon_end = current + timedelta(days=horizon)
        warehouses = run.warehouse_ids or self.env["stock.warehouse"].search([
            ("company_id", "=", run.company_id.id),
        ])

        ctx = {
            "current": current,
            "horizon_end": horizon_end,
            "warehouses": warehouses,
            "company_id": run.company_id.id,
        }

        items = self._collect_items(ctx)
        locations = self._collect_locations(ctx)
        customers = self._collect_customers(ctx)
        suppliers = self._collect_suppliers(ctx)
        item_suppliers = self._collect_item_suppliers(ctx, items)
        calendars = self._collect_calendars(ctx)
        resources = self._collect_resources(ctx, calendars)
        operations = self._collect_operations(ctx, items, resources, locations)
        buffers = self._collect_buffers(ctx, items, locations)
        demands = self._collect_demands(ctx, items, locations, customers)
        scheduled_receipts = self._collect_scheduled_receipts(ctx, items, locations)

        return {
            "current": current,
            "horizon_end": horizon_end,
            "calendars": calendars,
            "items": items,
            "locations": locations,
            "customers": customers,
            "suppliers": suppliers,
            "item_suppliers": item_suppliers,
            "resources": resources,
            "operations": operations,
            "buffers": buffers,
            "demands": demands,
            "scheduled_receipts": scheduled_receipts,
            "_counts": {
                "items": len(items),
                "locations": len(locations),
                "customers": len(customers),
                "suppliers": len(suppliers),
                "resources": len(resources),
                "operations": len(operations),
                "buffers": len(buffers),
                "demands": len(demands),
                "scheduled_receipts": len(scheduled_receipts),
            },
        }

    def _collect_items(self, ctx) -> list[dict]:
        products = self.env["product.product"].search([
            ("type", "in", ("consu", "product")),
            ("active", "=", True),
        ])
        out: list[dict] = []
        for p in products:
            out.append({
                "name": p.default_code or f"P{p.id}",
                "description": p.name,
                "category": p.categ_id.complete_name or "",
                "cost": p.standard_price,
                "price": p.list_price,
                "uom": p.uom_id.name,
                "_odoo_id": p.id,
            })
        return out

    def _collect_locations(self, ctx) -> list[dict]:
        warehouses = ctx["warehouses"]
        locations = self.env["stock.location"].search([
            ("usage", "in", ("internal", "transit")),
            ("warehouse_id", "in", warehouses.ids),
        ])
        out: list[dict] = []
        seen_wh: set[int] = set()
        for wh in warehouses:
            if wh.id in seen_wh:
                continue
            seen_wh.add(wh.id)
            out.append({
                "name": wh.code or wh.name,
                "description": wh.name,
                "_odoo_wh_id": wh.id,
            })
        for loc in locations:
            wh = loc.warehouse_id
            if not wh:
                continue
            out.append({
                "name": f"{wh.code}/{loc.name}",
                "description": loc.complete_name or loc.name,
                "owner": wh.code or wh.name,
                "_odoo_loc_id": loc.id,
            })
        return out

    def _collect_customers(self, ctx) -> list[dict]:
        partners = self.env["res.partner"].search([
            ("customer_rank", ">", 0),
            ("active", "=", True),
        ], limit=10000)
        return [
            {"name": f"C{p.id}", "description": p.name, "_odoo_id": p.id}
            for p in partners
        ]

    def _collect_suppliers(self, ctx) -> list[dict]:
        partners = self.env["res.partner"].search([
            ("supplier_rank", ">", 0),
            ("active", "=", True),
        ], limit=10000)
        return [
            {"name": f"S{p.id}", "description": p.name, "_odoo_id": p.id}
            for p in partners
        ]

    def _collect_item_suppliers(self, ctx, items) -> list[dict]:
        item_keys = {it["_odoo_id"]: it["name"] for it in items}
        supplierinfo = self.env["product.supplierinfo"].search([])
        out: list[dict] = []
        for info in supplierinfo:
            product = info.product_id or (
                info.product_tmpl_id.product_variant_ids[:1]
            )
            if not product or product.id not in item_keys:
                continue
            out.append({
                "item": item_keys[product.id],
                "supplier": f"S{info.partner_id.id}",
                "leadtime_days": info.delay or 0,
                "cost": info.price,
                "size_minimum": info.min_qty or 1.0,
                "priority": info.sequence or 1,
            })
        return out

    def _collect_calendars(self, ctx) -> list[dict]:
        cals = self.env["resource.calendar"].search([
            ("company_id", "in", (False, ctx["company_id"])),
        ])
        out: list[dict] = []
        for cal in cals:
            buckets: list[dict] = []
            for att in cal.attendance_ids:
                buckets.append({
                    "name": att.name,
                    "dayofweek": int(att.dayofweek),
                    "hour_from": att.hour_from,
                    "hour_to": att.hour_to,
                    "value": 1.0,
                })
            for leave in cal.leave_ids:
                buckets.append({
                    "name": leave.name or "leave",
                    "start_date": leave.date_from,
                    "end_date": leave.date_to,
                    "value": 0.0,
                    "priority": 100,
                })
            out.append({
                "name": cal.name,
                "default_value": 0.0,
                "buckets": buckets,
                "_odoo_id": cal.id,
            })
        return out

    def _collect_resources(self, ctx, calendars) -> list[dict]:
        workcenters = self.env["mrp.workcenter"].search([
            ("active", "=", True),
            ("company_id", "in", (False, ctx["company_id"])),
        ])
        cal_by_id = {c["_odoo_id"]: c["name"] for c in calendars}
        out: list[dict] = []
        for wc in workcenters:
            out.append({
                "name": wc.code or wc.name,
                "description": wc.name,
                "maximum": wc.default_capacity or 1.0,
                "cost_per_hour": wc.costs_hour or 0.0,
                "efficiency": wc.time_efficiency or 100.0,
                "calendar": cal_by_id.get(wc.resource_calendar_id.id),
                "_odoo_id": wc.id,
            })
        return out

    def _collect_operations(self, ctx, items, resources, locations) -> list[dict]:
        item_by_product = {it["_odoo_id"]: it["name"] for it in items}
        wh_name = locations[0]["name"] if locations else "WH"
        resource_by_wc = {r["_odoo_id"]: r["name"] for r in resources}
        boms = self.env["mrp.bom"].search([
            ("active", "=", True),
            ("company_id", "in", (False, ctx["company_id"])),
        ])
        out: list[dict] = []
        for bom in boms:
            product = bom.product_id or bom.product_tmpl_id.product_variant_ids[:1]
            if not product or product.id not in item_by_product:
                continue
            output_item = item_by_product[product.id]
            op_name = f"BOM/{bom.id}/{output_item}"
            flows: list[dict] = []
            for line in bom.bom_line_ids:
                in_product = line.product_id
                if in_product.id not in item_by_product:
                    continue
                flows.append({
                    "item": item_by_product[in_product.id],
                    "type": "start",
                    "quantity": -line.product_qty,
                })
            flows.append({
                "item": output_item,
                "type": "end",
                "quantity": bom.product_qty or 1.0,
            })

            loads: list[dict] = []
            for step in bom.operation_ids:
                wc_name = resource_by_wc.get(step.workcenter_id.id)
                if not wc_name:
                    continue
                cycle_h = (step.time_cycle or 0.0) / 60.0
                loads.append({
                    "resource": wc_name,
                    "quantity": 1.0,
                    "duration_hours": cycle_h,
                    "name": step.name,
                })

            out.append({
                "name": op_name,
                "type": "routing" if loads else "fixed_time",
                "item": output_item,
                "location": wh_name,
                "duration_hours": sum(l["duration_hours"] for l in loads) or 1.0,
                "size_minimum": bom.product_qty or 1.0,
                "flows": flows,
                "loads": loads,
                "_odoo_id": bom.id,
            })
        return out

    def _collect_buffers(self, ctx, items, locations) -> list[dict]:
        item_by_product = {it["_odoo_id"]: it["name"] for it in items}
        loc_by_id = {l.get("_odoo_loc_id"): l["name"] for l in locations if l.get("_odoo_loc_id")}
        quants = self.env["stock.quant"]._read_group(
            domain=[
                ("location_id.usage", "=", "internal"),
                ("product_id.id", "in", list(item_by_product.keys())),
            ],
            groupby=["product_id", "location_id"],
            aggregates=["quantity:sum"],
        )
        out: list[dict] = []
        for product, location, qty in quants:
            item_name = item_by_product.get(product.id)
            loc_name = loc_by_id.get(location.id)
            if not item_name or not loc_name:
                continue
            out.append({
                "item": item_name,
                "location": loc_name,
                "onhand": qty or 0.0,
            })
        return out

    def _collect_demands(self, ctx, items, locations, customers) -> list[dict]:
        item_by_product = {it["_odoo_id"]: it["name"] for it in items}
        customer_by_partner = {c["_odoo_id"]: c["name"] for c in customers}
        wh_name = locations[0]["name"] if locations else "WH"
        lines = self.env["sale.order.line"].search([
            ("order_id.state", "in", ("sale", "done")),
            ("product_uom_qty", ">", 0),
            ("company_id", "=", ctx["company_id"]),
        ])
        out: list[dict] = []
        for line in lines:
            qty_to_ship = (line.product_uom_qty or 0) - (line.qty_delivered or 0)
            if qty_to_ship <= 0:
                continue
            item_name = item_by_product.get(line.product_id.id)
            if not item_name:
                continue
            order = line.order_id
            due = order.commitment_date or order.date_order or ctx["current"]
            out.append({
                "name": f"SO/{order.id}/{line.id}",
                "item": item_name,
                "location": wh_name,
                "customer": customer_by_partner.get(order.partner_id.id),
                "quantity": qty_to_ship,
                "due": due,
                "priority": 10,
                "status": "open",
                "_odoo_line_id": line.id,
            })
        return out

    def _collect_scheduled_receipts(self, ctx, items, locations) -> list[dict]:
        item_by_product = {it["_odoo_id"]: it["name"] for it in items}
        wh_name = locations[0]["name"] if locations else "WH"
        lines = self.env["purchase.order.line"].search([
            ("order_id.state", "in", ("purchase", "done")),
            ("product_uom_qty", ">", 0),
            ("company_id", "=", ctx["company_id"]),
        ])
        out: list[dict] = []
        for line in lines:
            qty_open = (line.product_uom_qty or 0) - (line.qty_received or 0)
            if qty_open <= 0:
                continue
            item_name = item_by_product.get(line.product_id.id)
            if not item_name:
                continue
            order = line.order_id
            out.append({
                "operationplan_type": "PO",
                "status": "confirmed",
                "item": item_name,
                "location": wh_name,
                "supplier": f"S{order.partner_id.id}",
                "quantity": qty_open,
                "end_date": line.date_planned or ctx["current"],
                "reference": f"PO/{order.id}/{line.id}",
            })
        return out
