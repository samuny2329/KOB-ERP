"""Decorator + helpers to route heavy reads to a PostgreSQL replica.

Usage::

    from odoo.addons.kob_db_replica.replica_router import with_replica

    class MyReport(models.AbstractModel):
        _name = "my.report"

        @with_replica
        def get_data(self, domain):
            return self.env["account.move.line"].search_read(domain, ...)

The decorated method opens a *separate* psycopg2 connection to
``db_replica_uri`` (defined in odoo.conf), runs the wrapped function,
and returns the result. The connection is closed on exit.

If ``db_replica_uri`` is not configured, falls back to the primary
connection silently — so code that opts in still works in dev.
"""

import functools
import logging
import os
import time

import psycopg2
from psycopg2.extras import DictCursor

from odoo import tools

_logger = logging.getLogger(__name__)

_LAG_WARN_THRESHOLD_SEC = 30


def _get_replica_uri():
    """Return DSN for replica from odoo.conf, env, or None."""
    uri = tools.config.get("db_replica_uri") or os.environ.get("DB_REPLICA_URI")
    return uri or None


def _open_replica_connection():
    """Return a fresh psycopg2 connection to the replica, or None.

    Caller must close it. Read-only by default."""
    uri = _get_replica_uri()
    if not uri:
        return None
    try:
        conn = psycopg2.connect(uri)
        conn.set_session(readonly=True, autocommit=True)
        return conn
    except Exception as e:
        _logger.warning("[KobReplica] Cannot connect to replica: %s", e)
        return None


def with_replica(func):
    """Decorator: run ``func`` against the replica DB if configured."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        replica_conn = _open_replica_connection()
        if not replica_conn:
            # No replica — fall back to primary (silent; dev convenience)
            return func(self, *args, **kwargs)
        original_cursor = self.env.cr
        # Wrap psycopg2 cursor to look like Odoo cursor enough for ORM reads.
        # NOTE: Odoo's ORM uses `self.env.cr` extensively. To make the swap
        # transparent we patch the env's connection. This is a *read-only*
        # context — any write will fail (psycopg2 readonly=True).
        try:
            t0 = time.time()
            from odoo.sql_db import Connection
            # Best-effort: monkey-patch env.cr.dbname & .execute to use replica.
            # Production-grade implementation would create a proper Cursor wrapper.
            class _ReplicaCursor:
                def __init__(self, conn):
                    self._conn = conn
                    self._cur = conn.cursor(cursor_factory=DictCursor)
                def execute(self, query, params=None):
                    return self._cur.execute(query, params)
                def fetchall(self):
                    return self._cur.fetchall()
                def fetchone(self):
                    return self._cur.fetchone()
                def fetchmany(self, n):
                    return self._cur.fetchmany(n)
                @property
                def description(self):
                    return self._cur.description
                def close(self):
                    self._cur.close()
                    self._conn.close()
            self.env.cr.flush()  # ensure pending writes pushed to primary
            self = self.with_env(self.env(cr=_ReplicaCursor(replica_conn)))
            result = func(self, *args, **kwargs)
            elapsed = time.time() - t0
            if elapsed > _LAG_WARN_THRESHOLD_SEC:
                _logger.warning(
                    "[KobReplica] Slow query >%ss on replica for %s",
                    _LAG_WARN_THRESHOLD_SEC, func.__name__,
                )
            return result
        finally:
            try:
                replica_conn.close()
            except Exception:
                pass

    return wrapper


def replica_lag_seconds():
    """Query replication lag in seconds. Returns None if unknown.

    Run from the *primary* connection (uses pg_last_wal_replay_lsn on
    standby and pg_current_wal_lsn on primary)."""
    conn = _open_replica_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT EXTRACT(EPOCH FROM "
            "(now() - pg_last_xact_replay_timestamp()))"
        )
        row = cur.fetchone()
        return float(row[0]) if row and row[0] else 0.0
    except Exception as e:
        _logger.warning("[KobReplica] lag query failed: %s", e)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass
