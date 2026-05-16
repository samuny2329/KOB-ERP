import base64
run = env['thiti.plan.run'].search([('name', '=', 'PROD-test-1')], order='id desc', limit=1)
att = run.output_xml_attachment_id
if att and att.datas:
    raw = base64.b64decode(att.datas)
    print('size=', len(raw))
    print('head bytes (200):', repr(raw[:200]))
    print('tail bytes (200):', repr(raw[-200:]))
else:
    print('no attachment')
