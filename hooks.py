"""
Messaging module hook registrations.

Registers actions and filters on the HookRegistry during module load.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.hooks.registry import HookRegistry

MODULE_ID = "messaging"


def register_hooks(hooks: HookRegistry, module_id: str) -> None:
    """
    Register hooks for the messaging module.

    Called by ModuleRuntime during module load.
    """
    # Action: notify when a message is sent
    hooks.add_action(
        "messaging.message_sent",
        _on_message_sent,
        priority=10,
        module_id=module_id,
    )


async def _on_message_sent(message=None, **kwargs) -> None:
    """
    Hook called after a message is successfully sent.

    Other modules can listen to this to perform follow-up actions.
    """
