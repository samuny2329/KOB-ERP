# 🪐 Thiti Planning

**Advanced Planning & Scheduling** for KOB ERP — frePPLe Community engine
ported into a native Odoo 19 addon.

## What this is

- **Top-level Odoo app** "Thiti Planning" — menu icon visible after install
- **35 custom models** in 10 groups (master, demand/forecast, inventory,
  execution, output, auto-create, reports, scenarios, KOB-specific)
- **frePPLe C++ solver** invoked as subprocess from `bin/frepple`
- **Native Odoo views** — list/form/kanban/pivot/graph/gantt + 2 OWL components
- **Closed-loop planning** — auto-creates draft PO/MO/DO from solver output
- **REST API** — full CRUD + plan trigger via session or `X-Api-Key`
- **MIT engine + LGPL-3 addon** (frePPLe LICENSE kept in source tree)

## Install

### 1. Build the engine (once)

```bash
cd thiti-poc
docker build -f Dockerfile.poc -t thiti-poc:latest .
```

Produces `/src/bin/frepple` (binary, ~27 KB) and `/src/bin/libfrepple.so`
(~17 MB) inside the image.

### 2. Deploy engine to Odoo container

```bash
cid=$(docker create thiti-poc:latest)
docker cp "$cid:/src/bin/." ./engine-artifacts/
docker rm "$cid"

docker exec --user root <odoo-container> bash -c \
  "mkdir -p /opt/thiti/bin /opt/thiti/lib && chown -R odoo:odoo /opt/thiti"

docker cp ./engine-artifacts/frepple       <odoo-container>:/opt/thiti/bin/
docker cp ./engine-artifacts/libfrepple.so <odoo-container>:/opt/thiti/lib/
docker cp ./engine-artifacts/frepple.xsd   <odoo-container>:/opt/thiti/bin/
docker exec --user root <odoo-container> apt-get install -y \
  libxerces-c3.2 libpython3.12
```

### 3. Install the Odoo module

```bash
docker exec <odoo-container> odoo \
  -c /etc/odoo/odoo.conf \
  -d <db-name> \
  -i kob_thiti_planning \
  --stop-after-init --no-http
```

### 4. Configure

Open **Thiti Planning → Configuration → Settings** and tweak:
- Auto-create PO/MO/DO flags + horizons
- Engine binary path (default `/opt/thiti/bin/frepple`)
- Engine timeout (default 600s)

## Run a plan

1. **Thiti Planning → Execute → Plan Runs → New**
2. Set horizon + constraint level (15 = full, 7 = material only, 0 = unconstrained)
3. Click **Run Plan**

State transitions: `draft → collecting → solving → parsing → done`

Outputs land in:
- **Execute → Plan Operations** (list/form/gantt)
- **Execute → Demand Pegging**
- **Execute → Resource Load** (pivot + graph)
- **Execute → Buffer Projection** (line graph)
- **Execute → Problems** (kanban by severity)
- **Execute → Replenishment** (auto-created PO/MO/DO drafts)
- **Reports → KPI Scorecard**

## Data mapping (Odoo → solver)

| frePPLe entity | Odoo source |
|---|---|
| `<item>` | `product.product` (type=product/consu, active) |
| `<location>` | `stock.warehouse` + `stock.location` (internal) |
| `<calendar>` | `resource.calendar` + attendance + leaves |
| `<resource>` | `mrp.workcenter` (capacity + cost_hour + efficiency) |
| `<operation type="routing">` | `mrp.bom` + bom_line (flows) + routing.workcenter (loads) |
| `<buffer>` | `stock.quant._read_group(product × location)` |
| `<demand>` | `sale.order.line` (state in sale/done, qty_to_ship > 0) |
| `<itemsupplier>` | `product.supplierinfo` |
| `<operationplan type="PO" status="confirmed">` | `purchase.order.line` (open) |

## Auto-create rules

Every doc tagged with `origin = "THITI/<run.name>"`.

- **PO** grouped by `(supplier, ISO week)` — one PO per group with N lines
- **MO** one per (BOM, scheduled_date, qty) with auto BOM resolution
- **DO** grouped by `(src_wh, dst_wh, day)` — internal picking type lookup

Horizon gates: PO 30 days, MO 14 days, DO 7 days (configurable). Re-run
cancels prior `state='draft'` docs sharing the same origin. Confirmed/sent
docs are NEVER touched.

## REST API

Base path: `/thiti/api/`. Auth via Odoo session or header
`X-Api-Key: <res.users.apikeys key, scope='thiti'>`.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/thiti/api/<resource>` | list (limit/offset/order params) |
| GET | `/thiti/api/<resource>/<id>` | read one |
| GET | `/thiti/api/plan/<id>/operations` | plan ops |
| GET | `/thiti/api/plan/<id>/problems` | plan problems |
| GET | `/thiti/api/plan/<id>/kpi` | KPI scorecard |
| POST | `/thiti/api/plan/<id>/run` | trigger pipeline (planner+) |
| POST | `/thiti/api/import/<resource>` | bulk CSV import (planner+) |

`<resource>` ∈ item, location, customer, supplier, resource, buffer,
operation, demand, forecast, plan.

## Scenarios / what-if

**Execute → Scenarios** lets you clone the baseline + tweak
`capacity_factor`, `demand_factor`, `leadtime_factor`, then run plans
under that scenario. **Compare Scenarios** wizard renders KPI deltas
side-by-side.

## Tests

```bash
docker exec <odoo-container> odoo \
  -c /etc/odoo/odoo.conf -d <db-name> \
  --test-tags thiti \
  -i kob_thiti_planning --stop-after-init
```

5 test classes cover: data collector, XML serializer, XML parser, end-to-end
pipeline, KPI compute.

## KOB-specific extensions

- `thiti.kob.brand.line` — SWB / SWH / etc. with boat-carrier flag,
  crate-required flag, bottles per crate, extra lead time
- `thiti.item.kob_brand_line_id` link extends `thiti.item`
- Crate logistics (LWN-190A 30-bottle pool, 4 kg empty) modelable as
  `thiti.resource` with bucket capacity for forklift 2.5T tonnage limit

## Architecture

```
Odoo 19 container (kob-odoo-19)
└── kob_thiti_planning addon
    ├── 35 custom models (Groups A-J)
    ├── Native Odoo views (list/form/kanban/pivot/graph/gantt)
    ├── 2 OWL components (Dashboard + Gantt)
    ├── REST API controllers
    ├── data_collector  Odoo → Python dict
    ├── xml_serializer  dict → frePPLe XML
    ├── solver_wrapper  subprocess(bin/frepple)
    ├── xml_parser      output XML → thiti.plan.* records
    ├── auto_creator    plan output → draft PO/MO/Picking
    └── kpi             per-run scorecard

Postgres kobdb (shared with Odoo, single source of truth)

/opt/thiti/bin/frepple        — engine entry binary
/opt/thiti/lib/libfrepple.so  — C++ shared library
```

## License

- **Addon**: LGPL-3
- **Engine** (frePPLe Community): MIT — see `static/lib/LICENSE` for the
  copy distributed with the engine
