# Module Flows — Step-by-step

Each `.md` in this folder walks one KOB-ERP module from "user clicks Create" all
the way to "record is fully resolved", documents which states it can be in,
and points at the **Odoo 18** + **Odoo 19** sources we used as architectural
reference (we don't copy Odoo code — see [../ARCHITECTURE.md](../ARCHITECTURE.md)
§ "License-safe porting").

## Reference roots

| Reference | Local | Remote |
|-----------|-------|--------|
| Odoo 18 | `C:\Users\kobnb\Desktop\odoo-18.0` (read-only) | https://github.com/odoo/odoo/tree/18.0 |
| Odoo 19 (master / dev) | `C:\Users\kobnb\Desktop\odoo-19.0` (shallow clone, blob-filtered) | https://github.com/odoo/odoo/tree/master |
| KOB-WMS addon | `C:\Users\kobnb\Desktop\odoo-18.0\custom_addons\kob_wms` | (private) |

## Module index

| # | File | KOB-ERP module | Phase |
|---|------|----------------|-------|
| 00 | [00-core.md](00-core.md) | core (user / group / permission / company / audit / events) | 1 + 9 |
| 01 | [01-wms.md](01-wms.md) | wms (warehouse, zone, location, product, lot, uom) | 2a |
| 02 | [02-inventory.md](02-inventory.md) | inventory (stock_quant, transfer, transfer_line) | 2a |
| 03 | [03-outbound.md](03-outbound.md) | outbound (order, dispatch_batch, scan_item) + rack/pickface/courier | 2b |
| 04 | [04-counts.md](04-counts.md) | inventory.counts (session/task/entry/adjustment/snapshot) | 2c |
| 05 | [05-quality.md](05-quality.md) | quality (check, defect) | 2c |
| 06 | [06-ops.md](06-ops.md) | ops (box, platform, kpi, sla, worker, expiry, reports) | 2d |
| 07 | [07-purchase.md](07-purchase.md) | purchase (vendor, PO, receipt) | 3 |
| 08 | [08-mfg.md](08-mfg.md) | mfg (BoM, MO, work order, subcon) | 3 |
| 09 | [09-sales.md](09-sales.md) | sales (customer, SO, delivery) | 4 |
| 10 | [10-accounting.md](10-accounting.md) | accounting (CoA, journal, journal_entry, tax) | 5 |
| 11 | [11-hr.md](11-hr.md) | hr (department, employee, attendance, leave, payslip) | 6 |
| 12 | [12-audit.md](12-audit.md) | core.activity_log (SHA-256 hash-chain) | 2b |

## How to read a flow file

Each file follows the same shape so the differences pop out:

```
## Reference
- Odoo 18: <local path> + <github url>
- Odoo 19: <local path>      + <github url>

## KOB-ERP files
- backend/...
- frontend/...

## Data shape
Tables, fields, relations.

## State machine
Where applicable — allowed_transitions table.

## Happy-path flow
Numbered steps from the user perspective.

## Hooks / side-effects
What writes to audit log, what events fire, what other modules react.

## Differences vs Odoo
Why we deviate (license-safe re-implementation, scope reduction, etc).
```

## License note

We **read** Odoo source code to understand patterns and field shapes.  We
**re-implement from scratch** in SQLAlchemy / FastAPI / React.  No Odoo
file is copied verbatim.  See [../ARCHITECTURE.md](../ARCHITECTURE.md)
for the full porting policy.
