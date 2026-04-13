"""
Messaging module manifest.

Customer communication via WhatsApp, SMS, and email with CRM automations.
"""


# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------
MODULE_ID = "messaging"
MODULE_NAME = "Messaging"
MODULE_VERSION = "3.0.1-deprecated"  # functionality absorbed back into communications and whatsapp_inbox
MODULE_ICON = "chatbubbles-outline"
MODULE_DESCRIPTION = "Customer communication via WhatsApp, SMS, and email with CRM automations"
MODULE_AUTHOR = "ERPlora"
MODULE_CATEGORY = "marketing"

# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------
HAS_MODELS = True
MIDDLEWARE = ""

# ---------------------------------------------------------------------------
# Menu (sidebar entry)
# ---------------------------------------------------------------------------
MENU = {
    "label": "Messaging",
    "icon": "chatbubbles-outline",
    "order": 70,
}

# ---------------------------------------------------------------------------
# Navigation tabs (bottom tabbar in module views)
# ---------------------------------------------------------------------------
NAVIGATION = [
    {"id": "dashboard", "label": "Dashboard", "icon": "speedometer-outline", "view": "dashboard"},
    {"id": "inbox", "label": "Inbox", "icon": "mail-unread-outline", "view": "inbox"},
    {"id": "messages", "label": "Messages", "icon": "chatbubble-outline", "view": "messages"},
    {"id": "templates", "label": "Templates", "icon": "document-text-outline", "view": "templates"},
    {"id": "campaigns", "label": "Campaigns", "icon": "megaphone-outline", "view": "campaigns"},
    {"id": "automations", "label": "Automations", "icon": "flash-outline", "view": "automations"},
    {"id": "settings", "label": "Settings", "icon": "settings-outline", "view": "settings"},
]

# ---------------------------------------------------------------------------
# Dependencies (other modules required to be active)
# ---------------------------------------------------------------------------
DEPENDENCIES: list[str] = ["customers"]

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
PERMISSIONS = [
    ("view_message", "View messages"),
    ("send_message", "Send messages"),
    ("view_template", "View templates"),
    ("add_template", "Add templates"),
    ("change_template", "Edit templates"),
    ("delete_template", "Delete templates"),
    ("view_campaign", "View campaigns"),
    ("add_campaign", "Add campaigns"),
    ("view_automation", "View automations"),
    ("add_automation", "Add automations"),
    ("change_automation", "Edit automations"),
    ("delete_automation", "Delete automations"),
    ("manage_settings", "Manage settings"),
]

ROLE_PERMISSIONS = {
    "admin": ["*"],
    "manager": [
        "add_automation",
        "add_campaign",
        "add_template",
        "change_automation",
        "change_template",
        "send_message",
        "view_automation",
        "view_campaign",
        "view_message",
        "view_template",
    ],
    "employee": [
        "send_message",
        "view_automation",
        "view_campaign",
        "view_message",
        "view_template",
    ],
}

# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------
SCHEDULED_TASKS: list[dict] = []

# ---------------------------------------------------------------------------
# Pricing (free module)
# ---------------------------------------------------------------------------
# PRICING = {"monthly": 0, "yearly": 0}
