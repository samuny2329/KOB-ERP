from odoo import models, fields, tools


class WmsWorkerPerformance(models.Model):
    """SQL view: daily worker KPI with error rate, difficulty, score.

    Primary grouping is by kob.wms.user (PIN-login worker).
    Records without a kob worker (old data / admin-direct scans) are grouped
    separately under the Odoo user as a fallback.
    """
    _name = 'wms.worker.performance'
    _description = 'WMS Worker Daily Performance'
    _auto = False
    _order = 'date desc, kob_user_id'

    date = fields.Date(
        string='Date', readonly=True,
        help="Calendar day (truncated from wms.activity.log.create_date) used to "
             "group all of this worker's actions into one daily KPI row.",
    )
    kob_user_id = fields.Many2one(
        'kob.wms.user', string='Employee', readonly=True,
        help="WMS picker/packer profile (PIN login). Each kob.wms.user maps to "
             "one warehouse worker. If empty, look at 'Odoo User' for fallback "
             "attribution (admin-direct scans, pre-rollout data).",
    )
    user_id = fields.Many2one(
        'res.users', string='Odoo User', readonly=True,
        help="Odoo backend account that performed the scan when no kob.wms.user "
             "was attached. Used as a fallback so historic admin scans aren't "
             "lost from the KPI feed.",
    )

    # ─── Action counts ────────────────────────────────────────────────
    pick_count = fields.Integer(
        string='Picks', readonly=True,
        help="Number of pick scans (action='pick') in wms.activity.log for this "
             "day. Target ≥ 80/shift for 1 picker; <30 may indicate idle time.",
    )
    pack_count = fields.Integer(
        string='Packs', readonly=True,
        help="Number of pack scans (action='pack'). Each represents one order "
             "fully packed and sealed. Target ≥ 60/shift; <20 suggests "
             "bottleneck or low order volume.",
    )
    box_count = fields.Integer(
        string='Boxes', readonly=True,
        help="Boxes consumed (one per pack scan that closed a box). High "
             "ratio of Boxes to Packs (>1.2) means too many oversized boxes "
             "selected — review box recommender.",
    )
    ship_count = fields.Integer(
        string='Ships', readonly=True,
        help="Outbound scans (action='ship'). Target = pack_count when "
             "every packed order leaves the same day. Gap = backlog.",
    )
    scan_count = fields.Integer(
        string='Scans', readonly=True,
        help="Other generic scans (lookup, search, validate). Diagnostic "
             "metric — high without picks/packs = wasted motion.",
    )
    dispatch_count = fields.Integer(
        string='Dispatches', readonly=True,
        help="Courier batch dispatches (action='dispatch'). One per courier "
             "pickup. Typically 1–3 per day per warehouse.",
    )
    total_actions = fields.Integer(
        string='Total Actions', readonly=True,
        help="Sum of pick + pack + ship + scan + dispatch. The volume "
             "headline. Compare across workers to spot under-performers.",
    )

    # ─── Error counts ─────────────────────────────────────────────────
    pick_errors = fields.Integer(
        string='Pick Errors', readonly=True,
        help="Wrong-SKU or wrong-bin pick scans (note like 'SKU not found', "
             "'wrong location'). Acceptable: 0–2/day. Investigate ≥ 5/day.",
    )
    pack_errors = fields.Integer(
        string='Pack Errors', readonly=True,
        help="Pack-stage errors (oversize box, broken seal, missing AWB). "
             "Acceptable: 0–2/day. ≥ 5/day = retraining needed.",
    )
    total_errors = fields.Integer(
        string='Total Errors', readonly=True,
        help="Sum of all error logs. Combine with Total Actions to compute "
             "Error Rate. Target trend: monotonically decreasing.",
    )

    # ─── Rates ────────────────────────────────────────────────────────
    uph = fields.Float(
        string='UPH (8h)', readonly=True, digits=(10, 2),
        help="Units Per Hour over an 8-hour shift = total_actions / 8. "
             "Industry benchmark for cosmetics SKU picking: 50-80 UPH. "
             "🟢 ≥60 excellent · 🟡 40-60 OK · 🔴 <40 needs review.",
    )
    error_rate = fields.Float(
        string='Error Rate %', readonly=True, digits=(5, 2),
        help="(total_errors / total_actions) × 100. "
             "🟢 ≤2% target · 🟡 2–5% warning · 🔴 >5% retraining/SOP fix. "
             "Color decoration applied automatically in list view.",
    )
    quality_score = fields.Float(
        string='Quality %', readonly=True, digits=(5, 2),
        help="100 − error_rate. Inverse of error rate for easier KPI dashboards. "
             "🟢 ≥98% excellent · 🟡 95–97% acceptable · 🔴 <95% intervention.",
    )

    # ─── Composite Score ──────────────────────────────────────────────
    worker_score = fields.Float(
        string='Worker Score', readonly=True, digits=(10, 2),
        help="Composite: (UPH × Quality%) / 100. Balances speed and accuracy. "
             "🟢 ≥15 high-performer · 🟡 8–14 OK · 🔴 <8 below standard. "
             "Used in monthly bonus calculation and KPI assessments.",
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH kob_actions AS (
                    -- ── Group 1: kob.wms.user rows (real worker attribution) ──
                    SELECT
                        date_trunc('day', create_date)::date AS date,
                        kob_user_id,
                        NULL::integer                        AS user_id,
                        COUNT(*) FILTER (WHERE action = 'pick')       AS pick_count,
                        COUNT(*) FILTER (WHERE action = 'pack')       AS pack_count,
                        COUNT(*) FILTER (WHERE action = 'box')        AS box_count,
                        COUNT(*) FILTER (WHERE action = 'ship')       AS ship_count,
                        COUNT(*) FILTER (WHERE action = 'scan')       AS scan_count,
                        COUNT(*) FILTER (WHERE action = 'dispatch')   AS dispatch_count,
                        COUNT(*) FILTER (WHERE action = 'error_pick') AS pick_errors,
                        COUNT(*) FILTER (WHERE action = 'error_pack') AS pack_errors,
                        COUNT(*) FILTER (WHERE action NOT IN
                            ('error_pick','error_pack','login','logout','other'))
                                AS total_actions,
                        COUNT(*) FILTER (WHERE action IN ('error_pick','error_pack'))
                                AS total_errors
                    FROM wms_activity_log
                    WHERE kob_user_id IS NOT NULL
                    GROUP BY date_trunc('day', create_date), kob_user_id

                    UNION ALL

                    -- ── Group 2: Odoo-user fallback (no kob worker set) ──
                    SELECT
                        date_trunc('day', create_date)::date AS date,
                        NULL::integer                        AS kob_user_id,
                        user_id,
                        COUNT(*) FILTER (WHERE action = 'pick')       AS pick_count,
                        COUNT(*) FILTER (WHERE action = 'pack')       AS pack_count,
                        COUNT(*) FILTER (WHERE action = 'box')        AS box_count,
                        COUNT(*) FILTER (WHERE action = 'ship')       AS ship_count,
                        COUNT(*) FILTER (WHERE action = 'scan')       AS scan_count,
                        COUNT(*) FILTER (WHERE action = 'dispatch')   AS dispatch_count,
                        COUNT(*) FILTER (WHERE action = 'error_pick') AS pick_errors,
                        COUNT(*) FILTER (WHERE action = 'error_pack') AS pack_errors,
                        COUNT(*) FILTER (WHERE action NOT IN
                            ('error_pick','error_pack','login','logout','other'))
                                AS total_actions,
                        COUNT(*) FILTER (WHERE action IN ('error_pick','error_pack'))
                                AS total_errors
                    FROM wms_activity_log
                    WHERE kob_user_id IS NULL AND user_id IS NOT NULL
                    GROUP BY date_trunc('day', create_date), user_id
                )
                SELECT
                    -- Unique row ID: kob rows use kob_user_id slot; fallback uses 50000+user_id
                    CASE
                        WHEN kob_user_id IS NOT NULL
                            THEN (EXTRACT(EPOCH FROM date)::bigint * 100000 + kob_user_id)
                        ELSE     (EXTRACT(EPOCH FROM date)::bigint * 100000 + 50000 + user_id)
                    END AS id,
                    date,
                    kob_user_id,
                    user_id,
                    pick_count,
                    pack_count,
                    box_count,
                    ship_count,
                    scan_count,
                    dispatch_count,
                    total_actions,
                    pick_errors,
                    pack_errors,
                    total_errors,
                    ROUND(total_actions::numeric / 8.0, 2) AS uph,
                    CASE WHEN (total_actions + total_errors) > 0
                        THEN ROUND(total_errors::numeric / (total_actions + total_errors) * 100, 2)
                        ELSE 0 END AS error_rate,
                    CASE WHEN (total_actions + total_errors) > 0
                        THEN ROUND((1 - total_errors::numeric / (total_actions + total_errors)) * 100, 2)
                        ELSE 100 END AS quality_score,
                    CASE WHEN (total_actions + total_errors) > 0
                        THEN ROUND(
                            (total_actions::numeric / 8.0) *
                            (1 - total_errors::numeric / (total_actions + total_errors)) * 100
                        , 2)
                        ELSE 0 END AS worker_score
                FROM kob_actions
            )
        """)
