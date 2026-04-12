"""
Tests for MessageDispatcher.

Covers: successful dispatch via registered driver, fallback when no driver found.
"""

from __future__ import annotations

import pytest

from messaging.channels.base import (
    Capability,
    ChannelDriver,
    DeliveryReceipt,
    InboundMessage,
    OutboundMessage,
)
from messaging.channels.registry import register_driver, unregister_driver
from messaging.services.dispatcher import MessageDispatcher


# ---------------------------------------------------------------------------
# Minimal test driver
# ---------------------------------------------------------------------------

class EchoDriver(ChannelDriver):
    """Returns a sent receipt with echo of the body."""

    channel_id = "echo_test"
    display_name = "Echo Test"
    icon = "echo-outline"
    capabilities = {Capability.TEXT}

    async def send(self, msg: OutboundMessage) -> DeliveryReceipt:
        return DeliveryReceipt(
            external_message_id="echo-123",
            status="sent",
            raw={"echo": msg.body},
        )

    async def normalize_webhook(
        self,
        payload: dict,
        headers: dict | None = None,
    ) -> list[InboundMessage]:
        return []


@pytest.fixture(autouse=True)
def cleanup_echo():
    unregister_driver("echo_test")
    yield
    unregister_driver("echo_test")


def _make_msg(channel_id: str = "echo_test") -> OutboundMessage:
    return OutboundMessage(
        channel_id=channel_id,
        account_id="hub-abc",
        to_identifier="recipient@example.com",
        body="Hello from dispatcher test",
    )


class TestMessageDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_to_registered_driver(self):
        register_driver(EchoDriver())
        dispatcher = MessageDispatcher()
        receipt = await dispatcher.send(_make_msg("echo_test"))
        assert receipt.status == "sent"
        assert receipt.external_message_id == "echo-123"

    @pytest.mark.asyncio
    async def test_dispatch_to_unknown_channel_returns_failed(self):
        dispatcher = MessageDispatcher()
        receipt = await dispatcher.send(_make_msg("channel_that_does_not_exist_xyz"))
        assert receipt.status == "failed"
        assert receipt.external_message_id is None
        assert receipt.error is not None
        assert "channel_that_does_not_exist_xyz" in receipt.error

    @pytest.mark.asyncio
    async def test_dispatch_after_unregister_returns_failed(self):
        register_driver(EchoDriver())
        unregister_driver("echo_test")
        dispatcher = MessageDispatcher()
        receipt = await dispatcher.send(_make_msg("echo_test"))
        assert receipt.status == "failed"

    @pytest.mark.asyncio
    async def test_driver_send_is_delegated(self):
        """Dispatcher must delegate to driver.send(), not re-implement logic."""
        driver = EchoDriver()
        register_driver(driver)
        dispatcher = MessageDispatcher()
        msg = _make_msg("echo_test")
        receipt = await dispatcher.send(msg)
        assert receipt.raw.get("echo") == msg.body
