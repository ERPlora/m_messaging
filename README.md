# messaging — DEPRECATED

This module has been deprecated. Its functionality has been absorbed back into
the original specialist modules:

| Feature | Now lives in |
|---|---|
| SMTP + IMAP email driver | `communications` → `drivers/email_smtp.py` |
| WhatsApp Business driver | `whatsapp_inbox` → `drivers/whatsapp_business.py` |
| Meta webhook verification | `whatsapp_inbox` → `drivers/webhook.py` |
| Email templates | `communications` → `models.EmailTemplate` |
| WhatsApp templates | `whatsapp_inbox` → `models.WhatsAppTemplate` |
| Webhook endpoint (Meta) | `whatsapp_inbox` → `api.py` `/webhooks/meta/{account_id}` |
| AI tools for email inbox | `communications` → `services/module_services.py` |
| AI tools for WhatsApp | `whatsapp_inbox` → `services/module_services.py` |

## Why

The `messaging` module was created to provide a unified channel abstraction.
In practice, it created a dependency that `communications` and `whatsapp_inbox`
had to declare in order to function, which inverted the natural ownership.

The correct design is: each channel module owns its own driver, models, and
webhook endpoints. The `ChannelDriver` base classes are inlined where needed.

## Migration

1. Uninstall `messaging` from any active hubs.
2. Ensure `communications` (v2.0.0+) and `whatsapp_inbox` (v2.0.0+) are active.
3. Existing `communications_*` and `whatsapp_inbox_*` tables are unchanged.

## Date deprecated

2026-04-14
