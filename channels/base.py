"""
ChannelDriver base classes and DTOs for the unified messaging hub.

Every communication channel (WhatsApp Business, email SMTP, Telegram, SMS, etc.)
implements the ChannelDriver ABC and registers itself via channels.registry.
The dispatcher routes outbound messages without the core knowing about specific channels.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Capability(StrEnum):
    TEXT = "text"
    MEDIA = "media"
    TEMPLATES = "templates"
    BUTTONS = "buttons"
    THREADING = "threading"
    TYPING = "typing"
    REACTIONS = "reactions"


@dataclass
class Attachment:
    filename: str
    content_type: str
    url: str | None = None
    size: int | None = None


@dataclass
class InboundMessage:
    channel_id: str
    account_id: str
    external_thread_id: str
    external_message_id: str
    from_identifier: str          # phone, email, handle
    body: str
    attachments: list[Attachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    sent_at: str | None = None    # ISO 8601


@dataclass
class OutboundMessage:
    channel_id: str
    account_id: str
    to_identifier: str
    body: str
    attachments: list[Attachment] = field(default_factory=list)
    template_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryReceipt:
    external_message_id: str | None
    status: str                   # "sent" | "queued" | "failed"
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class ChannelDriver(ABC):
    """
    Abstract base for every messaging channel.

    Concrete drivers (e.g. WhatsAppDriver, EmailSMTPDriver) must:
    - Set class-level channel_id, display_name, icon, capabilities.
    - Implement send() and normalize_webhook().
    - Register themselves via channels.registry.register_driver().
    """

    channel_id: str = ""
    display_name: str = ""
    icon: str = ""
    capabilities: set[Capability] = set()

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> DeliveryReceipt:
        """Send an outbound message and return a delivery receipt."""
        ...

    @abstractmethod
    async def normalize_webhook(
        self,
        payload: dict,
        headers: dict | None = None,
    ) -> list[InboundMessage]:
        """
        Normalize a raw webhook payload into a list of InboundMessage objects.

        Returns an empty list if the payload contains no actionable messages.
        """
        ...

    async def validate_credentials(self, config: dict) -> bool:
        """
        Validate channel credentials (e.g. API keys, SMTP auth).

        Override to implement real credential validation. Default returns True
        so stubs/tests don't need to implement it.
        """
        return True

    async def sync_inbox(self, account: Any) -> None:
        """
        Pull-based inbox sync (for channels that don't push webhooks).

        Override for channels like IMAP email. Default is a no-op.
        """
        return None

    def supports_push(self) -> bool:
        """Return True if the channel delivers messages via webhook push."""
        return True
