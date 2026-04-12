"""
MessageDispatcher — routes outbound messages to the correct ChannelDriver.

Usage:
    from messaging.services.dispatcher import MessageDispatcher
    from messaging.channels.base import OutboundMessage

    dispatcher = MessageDispatcher()
    receipt = await dispatcher.send(OutboundMessage(
        channel_id="whatsapp",
        account_id="...",
        to_identifier="+34600000000",
        body="Hello!",
    ))
"""

from __future__ import annotations

from ..channels.base import DeliveryReceipt, OutboundMessage
from ..channels.registry import get_driver


class MessageDispatcher:
    """Routes OutboundMessage objects to the appropriate registered ChannelDriver."""

    async def send(self, msg: OutboundMessage) -> DeliveryReceipt:
        """
        Dispatch msg to the driver registered for msg.channel_id.

        Returns DeliveryReceipt(status="failed") if no driver is registered
        for the requested channel — this is intentional so callers can always
        inspect the receipt rather than catching exceptions.
        """
        driver = get_driver(msg.channel_id)
        if driver is None:
            return DeliveryReceipt(
                external_message_id=None,
                status="failed",
                error=f"No driver registered for channel '{msg.channel_id}'",
            )
        return await driver.send(msg)
