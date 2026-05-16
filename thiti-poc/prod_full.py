import time
t = time.monotonic()
# Use an existing draft run if available; else create new
run = env['thiti.plan.run'].create({
    'name': 'PROD-test-v2', 'plan_horizon_days': 30, 'constraint_level': '15',
})
print('=== START FULL RUN ===')
print('run id=%s name=%s state=%s' % (run.id, run.name, run.state))
try:
    run.action_run()
except Exception as e:
    print('EXC:', type(e).__name__, str(e)[:500])
env.cr.commit()
print('=== AFTER RUN ===')
print('state:', run.state, 'dur=%.2fs' % run.duration_seconds)
print('counts items=%s demands=%s ops=%s res=%s' % (
    run.item_count, run.demand_count, run.operation_count, run.resource_count,
))
print('output_xml:', run.output_xml_attachment_id.file_size if run.output_xml_attachment_id else 'NONE')
print('plan ops=%s pegs=%s loads=%s probs=%s reps=%s' % (
    env['thiti.plan.operation'].search_count([('run_id', '=', run.id)]),
    env['thiti.plan.demand.peg'].search_count([('run_id', '=', run.id)]),
    env['thiti.plan.resource.load'].search_count([('run_id', '=', run.id)]),
    env['thiti.plan.problem'].search_count([('run_id', '=', run.id)]),
    env['thiti.plan.replenishment'].search_count([('run_id', '=', run.id)]),
))
print('auto-created POs=%s MOs=%s' % (
    env['purchase.order'].search_count([('origin', '=', 'THITI/%s' % run.name)]),
    env['mrp.production'].search_count([('origin', '=', 'THITI/%s' % run.name)]),
))
kpi = env['thiti.kpi'].search([('run_id', '=', run.id)], limit=1)
if kpi:
    print('KPI: SL=%.1f%% util=%.1f%% delay=%.2fd' % (
        kpi.service_level_pct, kpi.capacity_utilization_pct, kpi.average_delay_days,
    ))
print('TOTAL elapsed=%.2fs' % (time.monotonic() - t))
print('LOG tail:', (run.log or '')[-300:])
print('ERR:', (run.error_message or '')[:500])
