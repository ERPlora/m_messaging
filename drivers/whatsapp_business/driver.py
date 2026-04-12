"""
WhatsApp Business API driver stub.

TODO (Fase 5): migrate full implementation from modules/whatsapp_inbox:
  - Webhook verification (X-Hub-Signature-256)
  - GPT-based message parser (whatsapp_inbox.services.gpt_parser)
  - Template message sending via Cloud API
  - Media upload + download
  - Delivery status webhook handling (sent/delivered/read)

For now this stub satisfies the ChannelDriver contract so the registry
and dispatcher work end-to-end without the whatsapp_inbox module.
"""

from __future__ import annotations

import logging
from typing import Any

from ...channels.base import (
    Capability,
    ChannelDriver,
    DeliveryReceipt,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger(__name__)


class WhatsAppDriver(ChannelDriver):
    """
    WhatsApp Business Cloud API driver.

    Stub implementation — full migration from whatsapp_inbox planned in Fase 5.
    """

    channel_id = "whatsapp"
    display_name = "WhatsApp Business"
    icon = "logo-whatsapp"
    capabilities = {
        Capability.TEXT,
        Capability.MEDIA,
        Capability.TEMPLATES,
        Capability.BUTTONS,
        Capability.THREADING,
        Capability.TYPING,
        Capability.REACTIONS,
    }

    async def send(self, msg: OutboundMessage) -> DeliveryReceipt:
        """
        Send a WhatsApp message via the Cloud API.

        STUB: logs and returns a queued receipt.
        Real implementation will call the WhatsApp Business Cloud API endpoint.
        """
        logger.info(
            "[WhatsAppDriver] STUB send to=%s body_len=%d",
            msg.to_identifier,
            len(msg.body),
        )
        return DeliveryReceipt(
            external_message_id=None,
            status="queued",
            error=None,
            raw={"stub": True, "to": msg.to_identifier},
        )

    async def normalize_webhook(
        self,
        payload: dict,
        headers: dict | None = None,
    ) -> list[InboundMessage]:
        """
        Normalize a WhatsApp webhook payload into InboundMessage list.

        STUB: returns empty list.
        Real implementation parses the Cloud API webhook format and emits
        MESSAGING_INBOUND_RECEIVED events via the EventBus.
        """
        logger.debug("[WhatsAppDriver] STUB normalize_webhook payload_keys=%s", list(payload))
        return []

    async def validate_credentials(self, config: dict) -> bool:
        """Validate WhatsApp Business API credentials."""
        required = ("whatsapp_api_token", "whatsapp_phone_id")
        return all(config.get(k) for k in required)

    def supports_push(self) -> bool:
        return True

    async def sync_inbox(self, account: Any) -> None:
        """WhatsApp is push-only; no pull sync needed."""
        return None
