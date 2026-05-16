from . import models
from . import wizards
from . import controllers


def post_init_hook(env):
    """Clean up orphaned data + drop stale NOT NULL constraints."""
    # Fix: wms_scan_wizard.order_id was required=True in v1, changed to
    # required=False in v2. The column constraint must be dropped manually
    # because Odoo doesn't always auto-drop NOT NULL on transient models.
    try:
        env.cr.execute("""
            ALTER TABLE wms_scan_wizard
            ALTER COLUMN order_id DROP NOT NULL
        """)
    except Exception:
        pass  # table might not exist yet on first install
    env.cr.execute(
        "DELETE FROM wms_courier WHERE id NOT IN ("
        "   SELECT res_id FROM ir_model_data"
        "   WHERE model = 'wms.courier' AND res_id IS NOT NULL)"
        " AND code IN ('EMS', 'FLS', 'JT', 'SPX', 'KISS')"
    )
    defaults = [
        ('EMS', 'Thailand Post', '#e11d48',
         'https://track.thailandpost.co.th/?trackNumber={barcode}'),
        ('FLS', 'Flash Express', '#f59e0b',
         'https://www.flashexpress.com/fle/tracking?se={barcode}'),
        ('JT', 'J&T Express', '#dc2626',
         'https://www.jtexpress.co.th/index/query/gzquery.html?bills={barcode}'),
        ('SPX', 'Shopee Express', '#f97316', ''),
        ('KISS', 'KISS Direct', '#3b82f6', ''),
    ]
    for code, name, color, tracking in defaults:
        existing = env['wms.courier'].search(
            [('code', '=', code)], limit=1)
        if not existing:
            env['wms.courier'].create({
                'code': code,
                'name': name,
                'color_hex': color,
                'tracking_url_template': tracking,
            })
    for platform in ('odoo', 'shopee', 'lazada', 'tiktok'):
        existing = env['wms.api.config'].search(
            [('platform', '=', platform)], limit=1)
        if not existing:
            env['wms.api.config'].create({
                'platform': platform,
                'enabled': platform == 'odoo',
            })

    # ── Audit Hash: Postgres trigger for real-time tamper detection ──
    # Fires AFTER UPDATE on wms_sales_order. Detects: data field changed
    # but audit_hash did not (silent psql tampering). Logs to activity
    # log + emits pg_notify on channel 'kob_audit_tamper'.
    try:
        env.cr.execute("""
            CREATE OR REPLACE FUNCTION kob_audit_tamper_trigger()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.audit_hash IS NOT NULL
                   AND NEW.audit_hash = OLD.audit_hash
                   AND (NEW.box_barcode IS DISTINCT FROM OLD.box_barcode
                        OR NEW.awb IS DISTINCT FROM OLD.awb
                        OR NEW.status IS DISTINCT FROM OLD.status
                        OR NEW.courier_id IS DISTINCT FROM OLD.courier_id
                        OR NEW.partner_id IS DISTINCT FROM OLD.partner_id)
                THEN
                    INSERT INTO wms_activity_log (
                        action, ref, code, note,
                        sales_order_id, user_id,
                        create_date, write_date, create_uid, write_uid,
                        prev_hash, block_hash
                    ) VALUES (
                        'tamper_detected_realtime',
                        OLD.name,
                        substr(OLD.audit_hash, 1, 16),
                        format('silent change: status %s->%s awb %s->%s',
                               OLD.status, NEW.status, OLD.awb, NEW.awb),
                        OLD.id,
                        COALESCE(NEW.write_uid, 1),
                        NOW(), NOW(),
                        COALESCE(NEW.write_uid, 1),
                        COALESCE(NEW.write_uid, 1),
                        '0',
                        encode(digest(OLD.audit_hash || NOW()::text,
                                      'sha256'), 'hex')
                    );
                    PERFORM pg_notify('kob_audit_tamper', OLD.name);
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        # pgcrypto needed for digest() in trigger
        env.cr.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        # Drop existing trigger first (idempotent re-install)
        env.cr.execute("""
            DROP TRIGGER IF EXISTS trg_kob_audit_check
            ON wms_sales_order;
        """)
        env.cr.execute("""
            CREATE TRIGGER trg_kob_audit_check
            AFTER UPDATE ON wms_sales_order
            FOR EACH ROW
            WHEN (OLD.audit_hash IS NOT NULL)
            EXECUTE FUNCTION kob_audit_tamper_trigger();
        """)
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            'audit trigger install skipped: %s', exc)
