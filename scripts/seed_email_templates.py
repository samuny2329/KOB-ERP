"""Seed common KOB email templates: PO confirmation, Invoice send, Helpdesk reply."""
env = self.env  # noqa: F821

# Models
po_model = env.ref("purchase.model_purchase_order").id
so_model = env.ref("sale.model_sale_order").id
am_model = env.ref("account.model_account_move").id
tk_model = env["ir.model"].search([("model", "=", "kob.helpdesk.ticket")], limit=1)

TEMPLATES = [
    {
        "name": "KOB — Purchase Order Confirmation",
        "model_id": po_model,
        "subject": "Purchase Order {{ object.name }} — KOB ERP",
        "email_from": "{{ object.company_id.email or 'noreply@kissofbeauty.co.th' }}",
        "email_to": "{{ object.partner_id.email }}",
        "body_html": (
            "<p>Dear {{ object.partner_id.name }},</p>"
            "<p>Please find attached our Purchase Order "
            "<strong>{{ object.name }}</strong> for "
            "<strong>{{ object.amount_total | round(2) }} {{ object.currency_id.name }}</strong>.</p>"
            "<p>Order date: {{ object.date_order }}<br/>"
            "Expected delivery: {{ object.date_planned or 'TBC' }}</p>"
            "<p>Best regards,<br/>{{ object.user_id.name }}<br/>"
            "Kiss of Beauty Co., Ltd.</p>"
        ),
    },
    {
        "name": "KOB — Sale Order Confirmation",
        "model_id": so_model,
        "subject": "Order Confirmation {{ object.name }} — KOB",
        "email_from": "{{ object.company_id.email or 'sales@kissofbeauty.co.th' }}",
        "email_to": "{{ object.partner_id.email }}",
        "body_html": (
            "<p>Dear {{ object.partner_id.name }},</p>"
            "<p>Thank you for your order! We have received your purchase "
            "<strong>{{ object.name }}</strong> for "
            "<strong>{{ object.amount_total | round(2) }} {{ object.currency_id.name }}</strong>.</p>"
            "<p>We will process and ship within 1-2 business days.</p>"
            "<p>Track your order: <a href='https://kissofbeauty.co.th/track/{{ object.name }}'>"
            "{{ object.name }}</a></p>"
            "<p>Warm regards,<br/>KOB Team</p>"
        ),
    },
    {
        "name": "KOB — Invoice Send",
        "model_id": am_model,
        "subject": "Invoice {{ object.name }} from KOB",
        "email_from": "{{ object.company_id.email or 'finance@kissofbeauty.co.th' }}",
        "email_to": "{{ object.partner_id.email }}",
        "body_html": (
            "<p>Dear {{ object.partner_id.name }},</p>"
            "<p>Please find attached invoice <strong>{{ object.name }}</strong> "
            "amounting to <strong>{{ object.amount_total | round(2) }} {{ object.currency_id.name }}</strong>.</p>"
            "<p>Due date: <strong>{{ object.invoice_date_due }}</strong></p>"
            "<p>Payment: Bank transfer to "
            "<br/>SCB 078-2-36509-3 (Kiss of Beauty Co., Ltd)<br/>"
            "Reference: {{ object.name }}</p>"
            "<p>Thank you for your business,<br/>KOB Finance</p>"
        ),
    },
    {
        "name": "KOB — Vendor Bill Reminder",
        "model_id": am_model,
        "subject": "Reminder: Bill {{ object.name }} due {{ object.invoice_date_due }}",
        "email_from": "{{ object.company_id.email or 'finance@kissofbeauty.co.th' }}",
        "email_to": "{{ object.partner_id.email }}",
        "body_html": (
            "<p>Dear {{ object.partner_id.name }},</p>"
            "<p>This is a reminder that bill "
            "<strong>{{ object.ref or object.name }}</strong> for "
            "<strong>{{ object.amount_total | round(2) }} {{ object.currency_id.name }}</strong> "
            "is due on <strong>{{ object.invoice_date_due }}</strong>.</p>"
            "<p>Please process payment at your earliest convenience.</p>"
            "<p>Thank you,<br/>KOB Finance</p>"
        ),
    },
]

if tk_model:
    TEMPLATES.append({
        "name": "KOB — Helpdesk Ticket Acknowledgement",
        "model_id": tk_model.id,
        "subject": "[Ticket {{ object.number }}] {{ object.name }}",
        "email_from": "{{ object.assignee_id.email or 'support@kissofbeauty.co.th' }}",
        "email_to": "{{ object.partner_id.email }}",
        "body_html": (
            "<p>Dear {{ object.partner_id.name or 'Customer' }},</p>"
            "<p>We have received your inquiry — ticket number "
            "<strong>{{ object.number }}</strong>.</p>"
            "<p><strong>Subject:</strong> {{ object.name }}<br/>"
            "<strong>Priority:</strong> {{ dict(object._fields['priority'].selection).get(object.priority) }}<br/>"
            "<strong>Assigned to:</strong> {{ object.assignee_id.name }}</p>"
            "<p>We will get back to you within 24 hours.</p>"
            "<p>Best regards,<br/>KOB Support Team</p>"
        ),
    })

created = 0
for t in TEMPLATES:
    existing = env["mail.template"].search([("name", "=", t["name"])], limit=1)
    if existing:
        existing.write({k: v for k, v in t.items() if k != "name"})
        print(f"  · {t['name']} updated")
        continue
    env["mail.template"].create(t)
    created += 1
    print(f"  ✓ {t['name']}")

env.cr.commit()
print(f"\n=== Final ===")
print(f"  Templates created: {created}")
print(f"  Total mail.template: {env['mail.template'].search_count([])}")
