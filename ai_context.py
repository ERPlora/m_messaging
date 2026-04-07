"""
Messaging module AI context -- injected into the LLM system prompt.

Provides the LLM with knowledge about the module's models, relationships,
and standard operating procedures.
"""

CONTEXT = """
## Messaging Module

Models: MessagingSettings, MessageTemplate, Message, Campaign, MessageAutomation, AutomationExecution.

### Channels
- WhatsApp (via Business API)
- SMS (via Twilio or MessageBird)
- Email (via SMTP)

### Message Templates
- Reusable templates with {{variable}} placeholders
- Categories: appointment_reminder, booking_confirmation, receipt, marketing, custom
- Can target specific channel or all channels
- Variables: {{customer_name}}, {{business_name}}, {{appointment_date}}, {{service_name}}, {{total_amount}}, etc.

### Campaigns
- Bulk messaging to customer segments
- Statuses: draft -> scheduled -> sending -> completed (or cancelled)
- Track recipients, sent count, delivered count, failed count
- Delivery rate and progress percentage

### Automations
- Triggered by CRM events: welcome, birthday, post_sale, post_appointment, inactivity, etc.
- Each automation has: trigger, channel, template, delay_hours, conditions
- Execution log tracks each send attempt

### Settings
- Per-hub configuration for WhatsApp API, SMS provider, SMTP
- Automation toggles for appointment reminders and booking confirmations

### Restrictions
- Template variables use {{variable}} syntax. Known variables: customer_name, business_name,
  appointment_date, appointment_time, service_name, staff_name, total_amount, booking_reference,
  order_reference, reservation_date, reservation_time, party_size, customer_phone, customer_email,
  hub_name, hub_phone, hub_address.
- Using undefined variables (not in the known list) will produce a warning but still allow creation.

### Key Relationships
- Message -> Customer (via customer_id FK)
- Message -> MessageTemplate (via template_id FK)
- Campaign -> MessageTemplate (via template_id FK)
- MessageAutomation -> MessageTemplate (via template_id FK)
- AutomationExecution -> MessageAutomation, Customer, Message
"""

SOPS = [
    {
        "id": "send_message",
        "triggers_es": ["enviar mensaje", "mandar mensaje", "escribir mensaje"],
        "triggers_en": ["send message", "compose message", "write message"],
        "steps": ["list_message_templates", "create_message_template"],
        "modules_required": ["messaging"],
    },
    {
        "id": "create_template",
        "triggers_es": ["crear plantilla", "nueva plantilla de mensaje"],
        "triggers_en": ["create template", "new message template"],
        "steps": ["create_message_template"],
        "modules_required": ["messaging"],
    },
    {
        "id": "create_automation",
        "triggers_es": ["crear automatizacion", "nueva automatizacion", "automatizar mensaje"],
        "triggers_en": ["create automation", "new automation", "automate message"],
        "steps": ["list_message_templates", "create_message_automation"],
        "modules_required": ["messaging"],
    },
]
