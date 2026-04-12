"""
SMTP email driver stub.

TODO (Fase 5): migrate full implementation from modules/communications:
  - aiosmtplib / smtplib async send
  - TLS/STARTTLS negotiation
  - Attachment support (multipart/mixed)
  - Per-hub SMTP settings from MessagingSettings
  - Bounce / delivery status tracking

For now this stub satisfies the ChannelDriver contract so the registry
and dispatcher work end-to-end without the communications module.
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


class EmailSMTPDriver(ChannelDriver):
    """
    SMTP email driver.

    Stub implementation — full migration from communications planned in Fase 5.
    """

    channel_id = "email_smtp"
    display_name = "Email (SMTP)"
    icon = "mail-outline"
    capabilities = {
        Capability.TEXT,
        Capability.MEDIA,
        Capability.THREADING,
    }

    async def send(self, msg: OutboundMessage) -> DeliveryReceipt:
        """
        Send an email via SMTP.

        STUB: logs and returns a queued receipt.
        Real implementation will use aiosmtplib with per-hub credentials
        from MessagingSettings.
        """
        logger.info(
            "[EmailSMTPDriver] STUB send to=%s subject=%s",
            msg.to_identifier,
            msg.metadata.get("subject", "(no subject)"),
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
        Normalize an inbound email payload.

        STUB: returns empty list.
        Real implementation would handle IMAP IDLE or email-to-webhook services.
        """
        logger.debug("[EmailSMTPDriver] STUB normalize_webhook")
        return []

    async def validate_credentials(self, config: dict) -> bool:
        """Validate SMTP credentials (host + username + password)."""
        required = ("email_smtp_host", "email_smtp_username", "email_smtp_password")
        return all(config.get(k) for k in required)

    def supports_push(self) -> bool:
        """SMTP is not push-based; use sync_inbox for pull-based retrieval."""
        return False

    async def sync_inbox(self, account: Any) -> None:
        """
        Pull new emails via IMAP.

        STUB: no-op. Real implementation uses imaplib/aioimaplib.
        """
        logger.debug("[EmailSMTPDriver] STUB sync_inbox - not yet implemented")
        return None
