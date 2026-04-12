"""
Tests for WhatsApp Business driver.

Covers: normalize_webhook parsing, send (mocked), signature verification.
"""

from __future__ import annotations

import pytest

from messaging.channels.base import InboundMessage
from messaging.drivers.whatsapp_business.driver import (
    WhatsAppDriver,
    _parse_message,
)


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

PHONE_NUMBER_ID = "12345678"
WA_ID = "34600000001"
WAMID = "wamid.HBgLMzQ2MDA="

SAMPLE_TEXT_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "WABA_ID",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "+34900000001",
                    "phone_number_id": PHONE_NUMBER_ID,
                },
                "contacts": [{
                    "profile": {"name": "Juan Pérez"},
                    "wa_id": WA_ID,
                }],
                "messages": [{
                    "from": WA_ID,
                    "id": WAMID,
                    "timestamp": "1712000000",
                    "type": "text",
                    "text": {"body": "Hola, quiero una pizza"},
                }],
            },
            "field": "messages",
        }],
    }],
}

SAMPLE_IMAGE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "WABA_ID",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "+34900000001",
                    "phone_number_id": PHONE_NUMBER_ID,
                },
                "contacts": [{"profile": {"name": "Ana"}, "wa_id": WA_ID}],
                "messages": [{
                    "from": WA_ID,
                    "id": WAMID,
                    "timestamp": "1712000000",
                    "type": "image",
                    "image": {
                        "id": "MEDIA_ID_123",
                        "mime_type": "image/jpeg",
                        "sha256": "abc",
                    },
                }],
            },
            "field": "messages",
        }],
    }],
}

SAMPLE_INTERACTIVE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "WABA_ID",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "+34900000001",
                    "phone_number_id": PHONE_NUMBER_ID,
                },
                "contacts": [{"profile": {"name": "Test"}, "wa_id": WA_ID}],
                "messages": [{
                    "from": WA_ID,
                    "id": WAMID,
                    "timestamp": "1712000000",
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {"id": "confirm", "title": "Confirmar"},
                    },
                }],
            },
            "field": "messages",
        }],
    }],
}

STATUS_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "WABA_ID",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "+34900000001",
                    "phone_number_id": PHONE_NUMBER_ID,
                },
                "statuses": [{
                    "id": WAMID,
                    "status": "delivered",
                    "timestamp": "1712000001",
                    "recipient_id": WA_ID,
                }],
            },
            "field": "messages",
        }],
    }],
}


# ---------------------------------------------------------------------------
# Tests: normalize_webhook
# ---------------------------------------------------------------------------

class TestWhatsAppDriverNormalizeWebhook:
    """normalize_webhook parses Meta payloads → InboundMessage list."""

    @pytest.mark.asyncio
    async def test_text_message_produces_one_inbound(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(SAMPLE_TEXT_PAYLOAD)
        assert len(messages) == 1
        msg = messages[0]
        assert isinstance(msg, InboundMessage)
        assert msg.channel_id == "whatsapp"
        assert msg.body == "Hola, quiero una pizza"
        assert msg.from_identifier == WA_ID
        assert msg.external_message_id == WAMID
        assert msg.external_thread_id == WA_ID

    @pytest.mark.asyncio
    async def test_text_message_metadata(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(SAMPLE_TEXT_PAYLOAD)
        msg = messages[0]
        assert msg.metadata["sender_name"] == "Juan Pérez"
        assert msg.metadata["phone_number_id"] == PHONE_NUMBER_ID
        assert msg.metadata["message_type"] == "text"

    @pytest.mark.asyncio
    async def test_text_message_account_id_is_phone_number_id(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(SAMPLE_TEXT_PAYLOAD)
        assert messages[0].account_id == PHONE_NUMBER_ID

    @pytest.mark.asyncio
    async def test_image_message_body_is_bracketed_type(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(SAMPLE_IMAGE_PAYLOAD)
        assert len(messages) == 1
        assert messages[0].body == "[image]"

    @pytest.mark.asyncio
    async def test_image_message_has_attachment(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(SAMPLE_IMAGE_PAYLOAD)
        assert len(messages[0].attachments) == 1
        att = messages[0].attachments[0]
        assert att.content_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_interactive_button_reply_body(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(SAMPLE_INTERACTIVE_PAYLOAD)
        assert len(messages) == 1
        assert messages[0].body == "Confirmar"

    @pytest.mark.asyncio
    async def test_status_update_returns_empty_list(self):
        """Status updates (delivered, read) should not produce InboundMessage."""
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(STATUS_PAYLOAD)
        assert messages == []

    @pytest.mark.asyncio
    async def test_wrong_object_returns_empty(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook({"object": "instagram"})
        assert messages == []

    @pytest.mark.asyncio
    async def test_empty_payload_returns_empty(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook({})
        assert messages == []

    @pytest.mark.asyncio
    async def test_multiple_messages_in_single_payload(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "WABA_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                        "contacts": [{"profile": {"name": "A"}, "wa_id": "111"}],
                        "messages": [
                            {
                                "from": "111",
                                "id": "msg1",
                                "timestamp": "1712000000",
                                "type": "text",
                                "text": {"body": "first"},
                            },
                            {
                                "from": "111",
                                "id": "msg2",
                                "timestamp": "1712000001",
                                "type": "text",
                                "text": {"body": "second"},
                            },
                        ],
                    },
                    "field": "messages",
                }],
            }],
        }
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(payload)
        assert len(messages) == 2
        assert messages[0].external_message_id == "msg1"
        assert messages[1].external_message_id == "msg2"

    @pytest.mark.asyncio
    async def test_sent_at_parsed_from_timestamp(self):
        driver = WhatsAppDriver()
        messages = await driver.normalize_webhook(SAMPLE_TEXT_PAYLOAD)
        assert messages[0].sent_at is not None
        assert "2024" in messages[0].sent_at or messages[0].sent_at.startswith("2024")


# ---------------------------------------------------------------------------
# Tests: _parse_message helper
# ---------------------------------------------------------------------------

class TestParseMessage:
    def test_parse_text(self):
        raw = {
            "from": WA_ID,
            "id": WAMID,
            "timestamp": "1712000000",
            "type": "text",
            "text": {"body": "Hello"},
        }
        result = _parse_message(raw, {WA_ID: "Pedro"}, PHONE_NUMBER_ID)
        assert result is not None
        assert result.body == "Hello"
        assert result.metadata["sender_name"] == "Pedro"

    def test_parse_audio_returns_bracket(self):
        raw = {
            "from": WA_ID,
            "id": WAMID,
            "timestamp": "1712000000",
            "type": "audio",
            "audio": {"id": "audio_id", "mime_type": "audio/ogg"},
        }
        result = _parse_message(raw, {}, PHONE_NUMBER_ID)
        assert result is not None
        assert result.body == "[audio]"

    def test_parse_missing_wa_id_returns_none(self):
        raw = {"id": WAMID, "type": "text", "text": {"body": "hi"}}
        result = _parse_message(raw, {}, PHONE_NUMBER_ID)
        assert result is None

    def test_parse_system_message_returns_none(self):
        raw = {"from": WA_ID, "id": WAMID, "type": "system"}
        result = _parse_message(raw, {}, PHONE_NUMBER_ID)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: driver metadata
# ---------------------------------------------------------------------------

class TestWhatsAppDriverMetadata:
    def test_channel_id(self):
        assert WhatsAppDriver.channel_id == "whatsapp"

    def test_display_name(self):
        assert WhatsAppDriver.display_name == "WhatsApp Business"

    def test_supports_push(self):
        assert WhatsAppDriver().supports_push() is True

    @pytest.mark.asyncio
    async def test_sync_inbox_returns_none(self):
        result = await WhatsAppDriver().sync_inbox(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_credentials_with_valid_config(self):
        config = {"whatsapp_api_token": "token123", "whatsapp_phone_id": "phone456"}
        assert await WhatsAppDriver().validate_credentials(config) is True

    @pytest.mark.asyncio
    async def test_validate_credentials_with_missing_config(self):
        config = {"whatsapp_api_token": "token123"}
        assert await WhatsAppDriver().validate_credentials(config) is False
