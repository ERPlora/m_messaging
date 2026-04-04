"""
Messaging module manifest.

Customer communication via WhatsApp, SMS, and email with CRM automations.
"""

from app.core.i18n import LazyString

# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------
MODULE_ID = "messaging"
MODULE_NAME = LazyString("Messaging", module_id="messaging")
MODULE_VERSION = "2.0.0"
MODULE_ICON = "chatbubbles-outline"
MODULE_DESCRIPTION = LazyString(
    "Customer communication via WhatsApp, SMS, and email with CRM automations",
    module_id="messaging",
)
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
    "label": LazyString("Messaging", module_id="messaging"),
    "icon": "chatbubbles-outline",
    "order": 70,
}

# ---------------------------------------------------------------------------
# Navigation tabs (bottom tabbar in module views)
# ---------------------------------------------------------------------------
NAVIGATION = [
    {"id": "dashboard", "label": LazyString("Dashboard", module_id="messaging"), "icon": "speedometer-outline", "view": "dashboard"},
    {"id": "messages", "label": LazyString("Messages", module_id="messaging"), "icon": "chatbubble-outline", "view": "messages"},
    {"id": "templates", "label": LazyString("Templates", module_id="messaging"), "icon": "document-text-outline", "view": "templates"},
    {"id": "campaigns", "label": LazyString("Campaigns", module_id="messaging"), "icon": "megaphone-outline", "view": "campaigns"},
    {"id": "automations", "label": LazyString("Automations", module_id="messaging"), "icon": "flash-outline", "view": "automations"},
    {"id": "settings", "label": LazyString("Settings", module_id="messaging"), "icon": "settings-outline", "view": "settings"},
]

# ---------------------------------------------------------------------------
# Dependencies (other modules required to be active)
# ---------------------------------------------------------------------------
DEPENDENCIES: list[str] = ["customers"]

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
PERMISSIONS = [
    ("view_message", LazyString("View messages", module_id="messaging")),
    ("send_message", LazyString("Send messages", module_id="messaging")),
    ("view_template", LazyString("View templates", module_id="messaging")),
    ("add_template", LazyString("Add templates", module_id="messaging")),
    ("change_template", LazyString("Edit templates", module_id="messaging")),
    ("delete_template", LazyString("Delete templates", module_id="messaging")),
    ("view_campaign", LazyString("View campaigns", module_id="messaging")),
    ("add_campaign", LazyString("Add campaigns", module_id="messaging")),
    ("view_automation", LazyString("View automations", module_id="messaging")),
    ("add_automation", LazyString("Add automations", module_id="messaging")),
    ("change_automation", LazyString("Edit automations", module_id="messaging")),
    ("delete_automation", LazyString("Delete automations", module_id="messaging")),
    ("manage_settings", LazyString("Manage settings", module_id="messaging")),
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
