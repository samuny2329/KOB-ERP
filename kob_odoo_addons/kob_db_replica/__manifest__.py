# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — DB Read-Replica Routing",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Infrastructure",
    "summary": "Route heavy read queries (reports, dashboards) to a "
               "PostgreSQL streaming replica. Backport of Odoo 20's "
               "read-replica DB support.",
    "description": """
KOB ERP — DB Read-Replica Routing
==================================

Route SELECT-only queries (reports, dashboards, BI exports) to a
PostgreSQL read-replica → primary handles writes only.

How it works
------------
1. Configure a replica DSN in odoo.conf via ``db_replica_uri``::

       db_replica_uri = postgresql://odoo:pass@replica-host:5432/kobdb

2. Wrap heavy read methods with ``@with_replica`` decorator from
   ``kob_db_replica.replica_router``::

       from odoo.addons.kob_db_replica.replica_router import with_replica

       class MyReport(models.AbstractModel):
           @with_replica
           def get_report_data(self, ...):
               return self.env["..."].search_read(...)

3. The decorator opens a separate cursor on the replica, runs the
   read, and returns the result. Writes attempted inside the
   decorated method raise an error.

Pre-req
-------
* PostgreSQL streaming replication setup (primary + standby)
* Read-only role on standby
* Lag monitor (warns if lag > 30s)

Limitations
-----------
* Replication lag may show stale data — prefer for non-critical reads
* Cannot route arbitrary writes (Odoo's tx model assumes single conn)
* Some Odoo internals (cache writes) still need primary
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/replica_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
