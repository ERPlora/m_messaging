"""
Test fixtures for the messaging module.
"""

from __future__ import annotations

import uuid

import pytest

from messaging.models import (
    Campaign,
    Message,
    MessageAutomation,
    MessageTemplate,
    MessagingSettings,
)


@pytest.fixture
def hub_id():
    """Test hub UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_template(hub_id):
    """Create a sample message template (not persisted)."""
    return MessageTemplate(
        hub_id=hub_id,
        name="Welcome Message",
        channel="email",
        category="custom",
        subject="Welcome to our service!",
        body="Hello {{customer_name}}, welcome to {{business_name}}!",
        is_active=True,
    )


@pytest.fixture
def sample_message(hub_id):
    """Create a sample message (not persisted)."""
    return Message(
        hub_id=hub_id,
        channel="email",
        recipient_name="John Doe",
        recipient_contact="john@example.com",
        subject="Test Subject",
        body="Test body",
        status="queued",
    )


@pytest.fixture
def sample_campaign(hub_id):
    """Create a sample campaign (not persisted)."""
    return Campaign(
        hub_id=hub_id,
        name="Spring Sale Campaign",
        description="Notify customers about spring sale",
        channel="email",
        status="draft",
        total_recipients=100,
    )


@pytest.fixture
def sample_automation(hub_id):
    """Create a sample automation (not persisted)."""
    return MessageAutomation(
        hub_id=hub_id,
        name="Welcome Automation",
        trigger="welcome",
        channel="email",
        delay_hours=0,
        is_active=True,
    )


@pytest.fixture
def sample_settings(hub_id):
    """Create sample messaging settings (not persisted)."""
    return MessagingSettings(
        hub_id=hub_id,
        whatsapp_enabled=False,
        sms_enabled=False,
        email_enabled=True,
    )
