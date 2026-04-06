"""
Messaging module models — SQLAlchemy 2.0.

Models: MessagingSettings, MessageTemplate, Message, Campaign,
        MessageAutomation, AutomationExecution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import HubBaseModel

if TYPE_CHECKING:
    pass


# ============================================================================
# Choice constants
# ============================================================================

CHANNEL_CHOICES = ("whatsapp", "sms", "email", "all")

MESSAGE_STATUS_CHOICES = ("queued", "sent", "delivered", "failed", "read")

CAMPAIGN_STATUS_CHOICES = ("draft", "scheduled", "sending", "completed", "cancelled")

SMS_PROVIDER_CHOICES = ("none", "twilio", "messagebird")

TEMPLATE_CATEGORY_CHOICES = (
    "appointment_reminder", "booking_confirmation", "receipt", "marketing", "custom",
)

AUTOMATION_TRIGGER_CHOICES = (
    "welcome", "birthday", "anniversary", "post_sale", "post_appointment",
    "inactivity", "loyalty_tier_change", "lead_stage_change", "ticket_resolved",
    "booking_confirmed", "booking_reminder", "custom",
)

EXECUTION_STATUS_CHOICES = ("pending", "sent", "failed", "skipped")

# Display labels for choices
CHANNEL_LABELS = {
    "whatsapp": "WhatsApp",
    "sms": "SMS",
    "email": "Email",
    "all": "All Channels",
}

MESSAGE_STATUS_LABELS = {
    "queued": "Queued",
    "sent": "Sent",
    "delivered": "Delivered",
    "failed": "Failed",
    "read": "Read",
}

CAMPAIGN_STATUS_LABELS = {
    "draft": "Draft",
    "scheduled": "Scheduled",
    "sending": "Sending",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

SMS_PROVIDER_LABELS = {
    "none": "None",
    "twilio": "Twilio",
    "messagebird": "MessageBird",
}

TEMPLATE_CATEGORY_LABELS = {
    "appointment_reminder": "Appointment Reminder",
    "booking_confirmation": "Booking Confirmation",
    "receipt": "Receipt",
    "marketing": "Marketing",
    "custom": "Custom",
}

AUTOMATION_TRIGGER_LABELS = {
    "welcome": "New Customer Welcome",
    "birthday": "Birthday",
    "anniversary": "Anniversary",
    "post_sale": "After Sale",
    "post_appointment": "After Appointment",
    "inactivity": "Customer Inactivity",
    "loyalty_tier_change": "Loyalty Tier Change",
    "lead_stage_change": "Lead Stage Change",
    "ticket_resolved": "Ticket Resolved",
    "booking_confirmed": "Booking Confirmed",
    "booking_reminder": "Booking Reminder",
    "custom": "Custom Trigger",
}

TRIGGER_ICONS = {
    "welcome": "hand-right-outline",
    "birthday": "gift-outline",
    "anniversary": "heart-outline",
    "post_sale": "cart-outline",
    "post_appointment": "calendar-outline",
    "inactivity": "time-outline",
    "loyalty_tier_change": "trophy-outline",
    "lead_stage_change": "funnel-outline",
    "ticket_resolved": "checkmark-done-outline",
    "booking_confirmed": "globe-outline",
    "booking_reminder": "alarm-outline",
    "custom": "code-outline",
}


# ============================================================================
# Messaging Settings
# ============================================================================

class MessagingSettings(HubBaseModel):
    """Per-hub messaging configuration."""

    __tablename__ = "messaging_settings"
    __table_args__ = (
        UniqueConstraint("hub_id", name="uq_messaging_settings_hub"),
    )

    # WhatsApp
    whatsapp_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    whatsapp_api_token: Mapped[str] = mapped_column(
        String(500), default="", server_default="",
    )
    whatsapp_phone_id: Mapped[str] = mapped_column(
        String(50), default="", server_default="",
    )
    whatsapp_business_id: Mapped[str] = mapped_column(
        String(50), default="", server_default="",
    )

    # SMS
    sms_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    sms_provider: Mapped[str] = mapped_column(
        String(20), default="none", server_default="none",
    )
    sms_api_key: Mapped[str] = mapped_column(
        String(255), default="", server_default="",
    )
    sms_sender_name: Mapped[str] = mapped_column(
        String(11), default="", server_default="",
    )

    # Email
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    email_from_name: Mapped[str] = mapped_column(
        String(255), default="", server_default="",
    )
    email_from_address: Mapped[str] = mapped_column(
        String(254), default="", server_default="",
    )
    email_smtp_host: Mapped[str] = mapped_column(
        String(255), default="", server_default="",
    )
    email_smtp_port: Mapped[int] = mapped_column(
        Integer, default=587, server_default="587",
    )
    email_smtp_username: Mapped[str] = mapped_column(
        String(255), default="", server_default="",
    )
    email_smtp_password: Mapped[str] = mapped_column(
        String(255), default="", server_default="",
    )
    email_smtp_use_tls: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )

    # Automation
    appointment_reminder_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    appointment_reminder_hours: Mapped[int] = mapped_column(
        Integer, default=24, server_default="24",
    )
    booking_confirmation_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )

    def __repr__(self) -> str:
        return "<MessagingSettings>"


# ============================================================================
# Message Template
# ============================================================================

class MessageTemplate(HubBaseModel):
    """Reusable message templates with variable placeholders."""

    __tablename__ = "messaging_template"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(
        String(20), default="all", server_default="all",
    )
    category: Mapped[str] = mapped_column(
        String(30), default="custom", server_default="custom",
    )
    subject: Mapped[str] = mapped_column(String(255), default="", server_default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )

    # Relationships
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="template", lazy="selectin",
    )
    campaigns: Mapped[list[Campaign]] = relationship(
        "Campaign", back_populates="template", lazy="selectin",
    )
    automations: Mapped[list[MessageAutomation]] = relationship(
        "MessageAutomation", back_populates="template", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<MessageTemplate {self.name!r}>"

    @property
    def channel_display(self) -> str:
        return CHANNEL_LABELS.get(self.channel, self.channel)

    @property
    def category_display(self) -> str:
        return TEMPLATE_CATEGORY_LABELS.get(self.category, self.category)

    def render_body(self, context: dict | None = None) -> str:
        """Render template body with context variables."""
        if not context:
            return self.body
        result = self.body
        for key, value in context.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result

    def render_subject(self, context: dict | None = None) -> str:
        """Render template subject with context variables."""
        if not context:
            return self.subject
        result = self.subject
        for key, value in context.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result


# ============================================================================
# Message
# ============================================================================

class Message(HubBaseModel):
    """Sent message log."""

    __tablename__ = "messaging_message"
    __table_args__ = (
        Index("ix_messaging_message_hub_channel_status", "hub_id", "channel", "status", "created_at"),
    )

    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_name: Mapped[str] = mapped_column(
        String(255), default="", server_default="",
    )
    recipient_contact: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), default="", server_default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="queued", server_default="queued",
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("messaging_template.id", ondelete="SET NULL"), nullable=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("customers_customer.id", ondelete="SET NULL"), nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    error_message: Mapped[str] = mapped_column(Text, default="", server_default="")
    external_id: Mapped[str] = mapped_column(
        String(255), default="", server_default="",
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # Relationships
    template: Mapped[MessageTemplate | None] = relationship(
        "MessageTemplate", back_populates="messages", lazy="joined",
    )
    customer: Mapped[Any | None] = relationship(
        "Customer", foreign_keys=[customer_id], lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Message {self.channel} -> {self.recipient_contact}>"

    @property
    def channel_display(self) -> str:
        return CHANNEL_LABELS.get(self.channel, self.channel)

    @property
    def status_display(self) -> str:
        return MESSAGE_STATUS_LABELS.get(self.status, self.status)

    @property
    def channel_icon(self) -> str:
        icons = {
            "whatsapp": "logo-whatsapp",
            "sms": "chatbubble-outline",
            "email": "mail-outline",
        }
        return icons.get(self.channel, "chatbubble-outline")

    @property
    def status_color(self) -> str:
        colors = {
            "queued": "color-warning",
            "sent": "color-primary",
            "delivered": "color-success",
            "failed": "color-error",
            "read": "color-success",
        }
        return colors.get(self.status, "")

    def mark_sent(self) -> None:
        self.status = "sent"
        self.sent_at = datetime.now(UTC)

    def mark_delivered(self) -> None:
        self.status = "delivered"
        self.delivered_at = datetime.now(UTC)

    def mark_read(self) -> None:
        self.status = "read"
        self.read_at = datetime.now(UTC)

    def mark_failed(self, error: str = "") -> None:
        self.status = "failed"
        self.error_message = error


# ============================================================================
# Campaign
# ============================================================================

class Campaign(HubBaseModel):
    """Bulk messaging campaigns."""

    __tablename__ = "messaging_campaign"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("messaging_template.id", ondelete="SET NULL"), nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft",
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    total_recipients: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    sent_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    delivered_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    target_filter: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # Relationships
    template: Mapped[MessageTemplate | None] = relationship(
        "MessageTemplate", back_populates="campaigns", lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.name!r}>"

    @property
    def channel_display(self) -> str:
        return CHANNEL_LABELS.get(self.channel, self.channel)

    @property
    def status_display(self) -> str:
        return CAMPAIGN_STATUS_LABELS.get(self.status, self.status)

    @property
    def status_color(self) -> str:
        colors = {
            "draft": "",
            "scheduled": "color-warning",
            "sending": "color-primary",
            "completed": "color-success",
            "cancelled": "color-error",
        }
        return colors.get(self.status, "")

    @property
    def delivery_rate(self) -> float:
        if self.sent_count == 0:
            return 0
        return round((self.delivered_count / self.sent_count) * 100, 1)

    @property
    def progress_percent(self) -> float:
        if self.total_recipients == 0:
            return 0
        return round((self.sent_count / self.total_recipients) * 100, 1)

    def start(self) -> None:
        self.status = "sending"
        self.started_at = datetime.now(UTC)

    def complete(self) -> None:
        self.status = "completed"
        self.completed_at = datetime.now(UTC)

    def cancel(self) -> None:
        self.status = "cancelled"


# ============================================================================
# Message Automation (CRM triggers)
# ============================================================================

class MessageAutomation(HubBaseModel):
    """Automated messaging rules that fire on CRM events."""

    __tablename__ = "messaging_automation"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    trigger: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(
        String(20), default="email", server_default="email",
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("messaging_template.id", ondelete="SET NULL"), nullable=True,
    )
    delay_hours: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    conditions: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    total_sent: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    template: Mapped[MessageTemplate | None] = relationship(
        "MessageTemplate", back_populates="automations", lazy="joined",
    )
    executions: Mapped[list[AutomationExecution]] = relationship(
        "AutomationExecution", back_populates="automation", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MessageAutomation {self.name!r} ({self.trigger})>"

    @property
    def trigger_display(self) -> str:
        return AUTOMATION_TRIGGER_LABELS.get(self.trigger, self.trigger)

    @property
    def channel_display(self) -> str:
        return CHANNEL_LABELS.get(self.channel, self.channel)

    @property
    def trigger_icon(self) -> str:
        return TRIGGER_ICONS.get(self.trigger, "flash-outline")


# ============================================================================
# Automation Execution
# ============================================================================

class AutomationExecution(HubBaseModel):
    """Log of automation executions."""

    __tablename__ = "messaging_automation_execution"

    automation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("messaging_automation.id", ondelete="CASCADE"), nullable=False,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("customers_customer.id", ondelete="SET NULL"), nullable=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("messaging_message.id", ondelete="SET NULL"), nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending",
    )
    trigger_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    error_message: Mapped[str] = mapped_column(Text, default="", server_default="")
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    automation: Mapped[MessageAutomation] = relationship(
        "MessageAutomation", back_populates="executions",
    )

    def __repr__(self) -> str:
        return f"<AutomationExecution automation={self.automation_id} status={self.status}>"
