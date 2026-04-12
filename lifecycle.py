"""
Messaging module lifecycle hooks.

Called by ModuleRuntime during install/activate/deactivate/uninstall/upgrade.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def on_install(session: AsyncSession, hub_id: UUID) -> None:
    """Called after module installation + migration. Seed initial data if needed."""
    logger.info("Messaging module installed for hub %s", hub_id)


async def on_activate(session: AsyncSession, hub_id: UUID) -> None:
    """Called when module is activated. Register built-in channel drivers."""
    from .channels.registry import register_driver
    from .drivers.email_smtp.driver import EmailSMTPDriver
    from .drivers.whatsapp_business.driver import WhatsAppDriver

    register_driver(WhatsAppDriver())
    register_driver(EmailSMTPDriver())
    logger.info(
        "Messaging module activated for hub %s — drivers registered: whatsapp, email_smtp",
        hub_id,
    )


async def on_deactivate(session: AsyncSession, hub_id: UUID) -> None:
    """Called when module is deactivated. Unregister drivers and clean up caches."""
    from .channels.registry import unregister_driver

    unregister_driver("whatsapp")
    unregister_driver("email_smtp")
    logger.info("Messaging module deactivated for hub %s — drivers unregistered", hub_id)


async def on_uninstall(session: AsyncSession, hub_id: UUID) -> None:
    """Called before module uninstall. Final cleanup."""
    logger.info("Messaging module uninstalled for hub %s", hub_id)


async def on_upgrade(session: AsyncSession, hub_id: UUID, from_version: str, to_version: str) -> None:
    """Called when the module is updated. Run data migrations between versions."""
    logger.info(
        "Messaging module upgraded from %s to %s for hub %s",
        from_version, to_version, hub_id,
    )
