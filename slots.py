"""
Messaging module slot registrations.

No POS slots for messaging -- this file is a placeholder for future UI extensibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.slots import SlotRegistry

MODULE_ID = "messaging"


def register_slots(slots: SlotRegistry, module_id: str) -> None:
    """
    Register slot content for the messaging module.

    Called by ModuleRuntime during module load.
    """
    # Messaging does not inject into POS or other module UIs currently.
