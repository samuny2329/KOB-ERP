import time
t = time.monotonic()
run = env['thiti.plan.run'].create({
    'name': 'PROD-test-1', 'plan_horizon_days': 30, 'constraint_level': '15',
})
run.action_collect_preview()
env.cr.commit()
print('=== COLLECT ===')
print('state:', run.state, 'dur=%.2fs' % run.duration_seconds)
print('items=%s loc=%s buf=%s ops=%s res=%s dem=%s sup=%s' % (
    run.item_count, run.location_count, run.buffer_count,
    run.operation_count, run.resource_count, run.demand_count, run.supplier_count,
))
print('XML attachment:', run.input_xml_attachment_id.file_size, 'bytes')
print('total elapsed=%.2fs' % (time.monotonic() - t))
