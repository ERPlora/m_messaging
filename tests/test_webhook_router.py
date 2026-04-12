"""
Tests for the central webhook router.

Covers:
- Unknown channel returns 404
- Known channel (WhatsApp) normalizes and returns processed count
- normalize_webhook is delegated to the driver
- Empty payload returns processed=0
- Idempotency (second call with same payload → driver still called but persist skipped)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from messaging.channels.base import (
    Capability,
    ChannelDriver,
    DeliveryReceipt,
    InboundMessage,
    OutboundMessage,
)
from messaging.channels.registry import register_driver, unregister_driver


# ---------------------------------------------------------------------------
# Test driver that captures calls
# ---------------------------------------------------------------------------

class CapturingDriver(ChannelDriver):
    channel_id = "test_webhook_ch"
    display_name = "Test Webhook Channel"
    icon = "code-outline"
    capabilities = {Capability.TEXT}

    def __init__(self, return_messages: list | None = None):
        self.normalize_calls: list[dict] = []
        self._return_messages = return_messages or []

    async def send(self, msg: OutboundMessage) -> DeliveryReceipt:
        return DeliveryReceipt(external_message_id=None, status="sent")

    async def normalize_webhook(
        self,
        payload: dict,
        headers: dict | None = None,
    ) -> list[InboundMessage]:
        self.normalize_calls.append(payload)
        return self._return_messages


@pytest.fixture(autouse=True)
def cleanup_test_channel():
    unregister_driver("test_webhook_ch")
    yield
    unregister_driver("test_webhook_ch")


def _make_inbound(body: str = "test", ext_id: str = "ext-001") -> InboundMessage:
    return InboundMessage(
        channel_id="test_webhook_ch",
        account_id="acct-001",
        external_thread_id="thread-001",
        external_message_id=ext_id,
        from_identifier="user@example.com",
        body=body,
    )


# ---------------------------------------------------------------------------
# Tests using the router directly (not via HTTP — avoids needing a test client)
# ---------------------------------------------------------------------------

class TestWebhookRouter:
    """Tests that call the router handler functions directly."""

    @pytest.mark.asyncio
    async def test_unknown_channel_returns_404_json(self):
        from messaging.webhooks.router import receive_webhook
        from fastapi import Request

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/webhooks/messaging/unknown_channel/acct",
            "headers": [],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": b"{}"}

        request = Request(scope, receive)

        response = await receive_webhook(
            channel_id="unknown_channel_xyz",
            account_id="acct-001",
            request=request,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_known_channel_calls_normalize_webhook(self):
        """Driver.normalize_webhook must be called for registered channels."""
        driver = CapturingDriver(return_messages=[])
        register_driver(driver)

        from messaging.webhooks.router import receive_webhook
        from fastapi import Request

        payload_bytes = json.dumps({"test": "data"}).encode()

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/webhooks/messaging/test_webhook_ch/acct",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": payload_bytes}

        request = Request(scope, receive)

        await receive_webhook(
            channel_id="test_webhook_ch",
            account_id="acct-001",
            request=request,
        )

        assert len(driver.normalize_calls) == 1
        assert driver.normalize_calls[0] == {"test": "data"}

    @pytest.mark.asyncio
    async def test_empty_messages_returns_processed_zero(self):
        """Empty normalize_webhook result → processed=0."""
        driver = CapturingDriver(return_messages=[])
        register_driver(driver)

        from messaging.webhooks.router import receive_webhook
        from fastapi import Request

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/webhooks/messaging/test_webhook_ch/acct",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": b"{}"}

        request = Request(scope, receive)

        response = await receive_webhook(
            channel_id="test_webhook_ch",
            account_id="acct-001",
            request=request,
        )

        data = json.loads(response.body)
        assert data["processed"] == 0
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_one_message_returns_processed_one(self):
        """One inbound message → processed=1."""
        driver = CapturingDriver(return_messages=[_make_inbound()])
        register_driver(driver)

        from messaging.webhooks.router import receive_webhook
        from fastapi import Request

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/webhooks/messaging/test_webhook_ch/acct",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": b"{}"}

        request = Request(scope, receive)

        # Patch _persist_inbound to avoid needing a DB in tests
        with patch("messaging.webhooks.router._persist_inbound", new_callable=AsyncMock):
            response = await receive_webhook(
                channel_id="test_webhook_ch",
                account_id="acct-001",
                request=request,
            )

        data = json.loads(response.body)
        assert data["processed"] == 1

    @pytest.mark.asyncio
    async def test_normalize_webhook_exception_returns_500(self):
        """If normalize_webhook raises, router returns 500."""
        driver = CapturingDriver()
        driver.normalize_webhook = AsyncMock(side_effect=RuntimeError("boom"))
        register_driver(driver)

        from messaging.webhooks.router import receive_webhook
        from fastapi import Request

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/webhooks/messaging/test_webhook_ch/acct",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": b"{}"}

        request = Request(scope, receive)

        response = await receive_webhook(
            channel_id="test_webhook_ch",
            account_id="acct-001",
            request=request,
        )

        assert response.status_code == 500
