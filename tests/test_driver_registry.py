"""
Tests for the ChannelDriver registry.

Covers: register, get, list, unregister, and driver replacement.
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
from messaging.channels.registry import (
    get_driver,
    list_drivers,
    register_driver,
    unregister_driver,
)
from messaging.drivers.email_smtp.driver import EmailSMTPDriver
from messaging.drivers.whatsapp_business.driver import WhatsAppDriver


# ---------------------------------------------------------------------------
# Mock driver for isolated testing (avoids polluting the shared registry)
# ---------------------------------------------------------------------------

class MockDriver(ChannelDriver):
    channel_id = "mock_channel"
    display_name = "Mock Channel"
    icon = "code-outline"
    capabilities = {Capability.TEXT}

    def __init__(self):
        self.send_calls: list[OutboundMessage] = []

    async def send(self, msg: OutboundMessage) -> DeliveryReceipt:
        self.send_calls.append(msg)
        return DeliveryReceipt(
            external_message_id="mock-ext-id",
            status="sent",
            raw={"mock": True},
        )

    async def normalize_webhook(
        self,
        payload: dict,
        headers: dict | None = None,
    ) -> list[InboundMessage]:
        return []


# ---------------------------------------------------------------------------
# Fixture: clean up mock channel after each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_mock():
    """Ensure mock_channel is unregistered before and after each test."""
    unregister_driver("mock_channel")
    yield
    unregister_driver("mock_channel")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDriverRegistry:
    def test_register_and_get(self):
        driver = MockDriver()
        register_driver(driver)
        assert get_driver("mock_channel") is driver

    def test_get_nonexistent_returns_none(self):
        assert get_driver("nonexistent_channel_xyz") is None

    def test_unregister_removes_driver(self):
        driver = MockDriver()
        register_driver(driver)
        unregister_driver("mock_channel")
        assert get_driver("mock_channel") is None

    def test_unregister_nonexistent_is_noop(self):
        # Should not raise
        unregister_driver("never_registered_abc")

    def test_register_replaces_existing(self):
        driver1 = MockDriver()
        driver2 = MockDriver()
        register_driver(driver1)
        register_driver(driver2)
        assert get_driver("mock_channel") is driver2

    def test_list_drivers_includes_registered(self):
        driver = MockDriver()
        register_driver(driver)
        drivers = list_drivers()
        assert driver in drivers

    def test_list_drivers_excludes_unregistered(self):
        driver = MockDriver()
        register_driver(driver)
        unregister_driver("mock_channel")
        assert driver not in list_drivers()

    def test_list_drivers_returns_copy(self):
        """Mutating the returned list must not affect the registry."""
        initial = list_drivers()
        initial.clear()
        # Registry should still work — add and retrieve
        driver = MockDriver()
        register_driver(driver)
        assert get_driver("mock_channel") is driver


class TestBuiltinDrivers:
    def test_whatsapp_driver_channel_id(self):
        assert WhatsAppDriver.channel_id == "whatsapp"

    def test_email_smtp_driver_channel_id(self):
        assert EmailSMTPDriver.channel_id == "email_smtp"

    def test_whatsapp_driver_has_text_capability(self):
        assert Capability.TEXT in WhatsAppDriver.capabilities

    def test_email_smtp_driver_has_text_capability(self):
        assert Capability.TEXT in EmailSMTPDriver.capabilities

    def test_whatsapp_driver_supports_push(self):
        assert WhatsAppDriver().supports_push() is True

    def test_email_smtp_driver_not_push(self):
        assert EmailSMTPDriver().supports_push() is False
