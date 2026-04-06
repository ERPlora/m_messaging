"""
Pydantic schemas for messaging module.

Replaces Django forms -- used for request validation and form rendering.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================================
# Message
# ============================================================================

class MessageCreate(BaseModel):
    channel: str = Field(max_length=20)
    recipient_name: str = Field(default="", max_length=255)
    recipient_contact: str = Field(max_length=255)
    subject: str = Field(default="", max_length=255)
    body: str
    template_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None


class MessageResponse(BaseModel):
    id: uuid.UUID
    channel: str
    recipient_name: str
    recipient_contact: str
    subject: str
    body: str
    status: str
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    error_message: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Message Template
# ============================================================================

class MessageTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    channel: str = Field(default="all", max_length=20)
    category: str = Field(default="custom", max_length=30)
    subject: str = Field(default="", max_length=255)
    body: str = Field(min_length=1)
    is_active: bool = True


class MessageTemplateUpdate(BaseModel):
    name: str | None = None
    channel: str | None = None
    category: str | None = None
    subject: str | None = None
    body: str | None = None
    is_active: bool | None = None


# ============================================================================
# Campaign
# ============================================================================

class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    channel: str = Field(max_length=20)
    template_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    channel: str | None = None
    template_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None


# ============================================================================
# Messaging Settings
# ============================================================================

class MessagingSettingsUpdate(BaseModel):
    # WhatsApp
    whatsapp_enabled: bool | None = None
    whatsapp_api_token: str | None = None
    whatsapp_phone_id: str | None = None
    whatsapp_business_id: str | None = None
    # SMS
    sms_enabled: bool | None = None
    sms_provider: str | None = None
    sms_api_key: str | None = None
    sms_sender_name: str | None = None
    # Email
    email_enabled: bool | None = None
    email_from_name: str | None = None
    email_from_address: str | None = None
    email_smtp_host: str | None = None
    email_smtp_port: int | None = None
    email_smtp_username: str | None = None
    email_smtp_password: str | None = None
    email_smtp_use_tls: bool | None = None
    # Automation
    appointment_reminder_enabled: bool | None = None
    appointment_reminder_hours: int | None = None
    booking_confirmation_enabled: bool | None = None


# ============================================================================
# API Send
# ============================================================================

class APISendRequest(BaseModel):
    channel: str
    recipient_contact: str
    body: str
    recipient_name: str = ""
    subject: str = ""
    template_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    extra_metadata: dict = {}


class APISendResponse(BaseModel):
    success: bool
    message_id: str | None = None
    status: str | None = None
    error: str | None = None


# ============================================================================
# Webhook
# ============================================================================

class WebhookRequest(BaseModel):
    external_id: str
    status: str
    error: str = ""
