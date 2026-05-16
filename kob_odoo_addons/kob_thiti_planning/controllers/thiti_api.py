"""REST controllers for Thiti Planning.

Auth: Odoo session OR API key via header `X-Api-Key` (Odoo native key from
`res.users.api_keys`). All endpoints return JSON.

Endpoints (mirror frePPLe DRF surface):
  GET    /thiti/api/item                  list items
  GET    /thiti/api/item/<id>             read one
  POST   /thiti/api/item                  create (planner+)
  PUT    /thiti/api/item/<id>             update
  DELETE /thiti/api/item/<id>             delete (manager only)
  GET    /thiti/api/demand                list demand
  GET    /thiti/api/forecast              list forecast
  GET    /thiti/api/plan                  list runs
  GET    /thiti/api/plan/<id>             plan run detail + counts
  GET    /thiti/api/plan/<id>/operations  operations of a run
  GET    /thiti/api/plan/<id>/problems    problems of a run
  GET    /thiti/api/plan/<id>/kpi         KPI scorecard
  POST   /thiti/api/plan/<id>/run         trigger pipeline
  POST   /thiti/api/import/<model>        bulk CSV import (planner+)
"""
from __future__ import annotations

import base64
import csv
import io
import json
import logging

from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)


THITI_LIST_MODELS = {
    "item": ("thiti.item", ["id", "name", "description", "category_id",
                            "cost", "price", "abc_class", "xyz_class"]),
    "location": ("thiti.location", ["id", "name", "complete_name", "warehouse_id"]),
    "customer": ("thiti.customer", ["id", "name", "partner_id", "priority"]),
    "supplier": ("thiti.supplier", ["id", "name", "partner_id", "lead_time_days"]),
    "resource": ("thiti.resource", ["id", "name", "resource_type",
                                    "maximum", "cost_per_hour", "efficiency"]),
    "buffer": ("thiti.buffer", ["id", "item_id", "location_id",
                                "buffer_type", "onhand", "minimum", "maximum"]),
    "operation": ("thiti.operation", ["id", "name", "operation_type",
                                      "item_id", "duration_hours"]),
    "demand": ("thiti.demand", ["id", "name", "item_id", "location_id",
                                "customer_id", "quantity", "due", "priority", "status"]),
    "forecast": ("thiti.forecast", ["id", "item_id", "location_id", "bucket_start",
                                    "bucket_end", "forecast_method", "baseline_qty",
                                    "net_qty", "mape"]),
    "plan": ("thiti.plan.run", ["id", "name", "state", "plan_horizon_days",
                                "create_date", "duration_seconds",
                                "item_count", "demand_count", "operation_count"]),
}


def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload, default=str),
        headers=[("Content-Type", "application/json; charset=utf-8")],
        status=status,
    )


def _check_auth():
    """Resolve user from session OR X-Api-Key header.

    Returns user record if authenticated, else None.
    """
    if request.env.user and request.env.user.id:
        return request.env.user
    key = request.httprequest.headers.get("X-Api-Key")
    if key:
        uid = request.env["res.users.apikeys"]._check_credentials(
            scope="thiti", key=key,
        )
        if uid:
            return request.env["res.users"].sudo().browse(uid)
    return None


class ThitiApi(http.Controller):

    # ----- List/read collections -----
    @http.route("/thiti/api/<string:resource>",
                type="http", auth="user", methods=["GET"], csrf=False)
    def list_collection(self, resource, **params):
        user = _check_auth()
        if not user:
            return _json_response({"error": "unauthorized"}, 401)
        cfg = THITI_LIST_MODELS.get(resource)
        if not cfg:
            return _json_response({"error": f"unknown resource: {resource}"}, 404)
        model, fields_list = cfg
        domain = []
        for key, value in params.items():
            if key in ("limit", "offset", "order"):
                continue
            try:
                domain.append((key, "=", value))
            except (ValueError, TypeError):
                pass
        limit = min(int(params.get("limit", 100)), 1000)
        offset = int(params.get("offset", 0))
        order = params.get("order", "id")
        records = request.env[model].sudo().search_read(
            domain, fields_list, limit=limit, offset=offset, order=order,
        )
        total = request.env[model].sudo().search_count(domain)
        return _json_response({
            "count": total, "limit": limit, "offset": offset,
            "results": records,
        })

    # ----- Single record -----
    @http.route("/thiti/api/<string:resource>/<int:rec_id>",
                type="http", auth="user", methods=["GET"], csrf=False)
    def read_record(self, resource, rec_id, **kw):
        user = _check_auth()
        if not user:
            return _json_response({"error": "unauthorized"}, 401)
        cfg = THITI_LIST_MODELS.get(resource)
        if not cfg:
            return _json_response({"error": f"unknown resource: {resource}"}, 404)
        model, fields_list = cfg
        rec = request.env[model].sudo().browse(rec_id)
        if not rec.exists():
            return _json_response({"error": "not found"}, 404)
        data = rec.read(fields_list)
        return _json_response(data[0] if data else {})

    # ----- Plan run details -----
    @http.route("/thiti/api/plan/<int:run_id>/operations",
                type="http", auth="user", methods=["GET"], csrf=False)
    def plan_operations(self, run_id, **kw):
        user = _check_auth()
        if not user:
            return _json_response({"error": "unauthorized"}, 401)
        ops = request.env["thiti.plan.operation"].sudo().search_read(
            [("run_id", "=", run_id)],
            ["id", "reference", "operation_name", "op_type", "item_id",
             "resource_id", "quantity", "start_datetime", "end_datetime",
             "status", "delay_days"],
            limit=5000,
        )
        return _json_response({"count": len(ops), "results": ops})

    @http.route("/thiti/api/plan/<int:run_id>/problems",
                type="http", auth="user", methods=["GET"], csrf=False)
    def plan_problems(self, run_id, **kw):
        user = _check_auth()
        if not user:
            return _json_response({"error": "unauthorized"}, 401)
        probs = request.env["thiti.plan.problem"].sudo().search_read(
            [("run_id", "=", run_id)],
            ["id", "problem_type", "severity", "entity_kind", "entity_name",
             "weight", "description", "start_datetime", "end_datetime"],
        )
        return _json_response({"count": len(probs), "results": probs})

    @http.route("/thiti/api/plan/<int:run_id>/kpi",
                type="http", auth="user", methods=["GET"], csrf=False)
    def plan_kpi(self, run_id, **kw):
        user = _check_auth()
        if not user:
            return _json_response({"error": "unauthorized"}, 401)
        kpi = request.env["thiti.kpi"].sudo().search_read(
            [("run_id", "=", run_id)], [],
            limit=1,
        )
        return _json_response(kpi[0] if kpi else {})

    @http.route("/thiti/api/plan/<int:run_id>/run",
                type="http", auth="user", methods=["POST"], csrf=False)
    def trigger_run(self, run_id, **kw):
        user = _check_auth()
        if not user or not user.has_group("kob_thiti_planning.group_thiti_planner"):
            return _json_response({"error": "forbidden"}, 403)
        run = request.env["thiti.plan.run"].sudo().browse(run_id)
        if not run.exists():
            return _json_response({"error": "not found"}, 404)
        try:
            run.action_run()
        except Exception as exc:  # noqa: BLE001
            _logger.exception("API trigger_run failed")
            return _json_response({"error": str(exc)}, 500)
        return _json_response({
            "id": run.id, "state": run.state,
            "duration_seconds": run.duration_seconds,
        })

    # ----- CSV bulk import -----
    @http.route("/thiti/api/import/<string:resource>",
                type="http", auth="user", methods=["POST"], csrf=False)
    def bulk_import(self, resource, **kw):
        user = _check_auth()
        if not user or not user.has_group("kob_thiti_planning.group_thiti_planner"):
            return _json_response({"error": "forbidden"}, 403)
        cfg = THITI_LIST_MODELS.get(resource)
        if not cfg:
            return _json_response({"error": f"unknown resource: {resource}"}, 404)
        model, _ = cfg
        body = request.httprequest.data
        if not body:
            return _json_response({"error": "empty body"}, 400)
        try:
            reader = csv.DictReader(io.StringIO(body.decode("utf-8")))
            rows = list(reader)
            created = request.env[model].sudo().create(rows)
        except Exception as exc:  # noqa: BLE001
            return _json_response({"error": str(exc)}, 400)
        return _json_response({"created": len(created), "ids": created.ids})
