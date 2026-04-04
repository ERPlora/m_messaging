"""
Tests for messaging module models.
"""

from __future__ import annotations

from messaging.models import (
    AUTOMATION_TRIGGER_CHOICES,
    AUTOMATION_TRIGGER_LABELS,
    CAMPAIGN_STATUS_LABELS,
    CHANNEL_LABELS,
    MESSAGE_STATUS_LABELS,
    TEMPLATE_CATEGORY_LABELS,
    TRIGGER_ICONS,
)


class TestMessageTemplate:
    def test_repr(self, sample_template):
        assert "Welcome Message" in repr(sample_template)

    def test_channel_display(self, sample_template):
        assert sample_template.channel_display == "Email"

    def test_category_display(self, sample_template):
        assert sample_template.category_display == "Custom"

    def test_render_body_no_context(self, sample_template):
        result = sample_template.render_body()
        assert "{{customer_name}}" in result

    def test_render_body_with_context(self, sample_template):
        result = sample_template.render_body({"customer_name": "Alice", "business_name": "Shop"})
        assert "Alice" in result
        assert "Shop" in result
        assert "{{customer_name}}" not in result

    def test_render_subject_no_context(self, sample_template):
        assert sample_template.render_subject() == "Welcome to our service!"

    def test_render_subject_with_context(self, sample_template):
        sample_template.subject = "Hello {{customer_name}}"
        result = sample_template.render_subject({"customer_name": "Bob"})
        assert result == "Hello Bob"


class TestMessage:
    def test_repr(self, sample_message):
        assert "email" in repr(sample_message)
        assert "john@example.com" in repr(sample_message)

    def test_channel_display(self, sample_message):
        assert sample_message.channel_display == "Email"

    def test_status_display(self, sample_message):
        assert sample_message.status_display == "Queued"

    def test_channel_icon(self, sample_message):
        assert sample_message.channel_icon == "mail-outline"
        sample_message.channel = "whatsapp"
        assert sample_message.channel_icon == "logo-whatsapp"
        sample_message.channel = "sms"
        assert sample_message.channel_icon == "chatbubble-outline"

    def test_status_color(self, sample_message):
        assert sample_message.status_color == "color-warning"
        sample_message.status = "sent"
        assert sample_message.status_color == "color-primary"
        sample_message.status = "delivered"
        assert sample_message.status_color == "color-success"
        sample_message.status = "failed"
        assert sample_message.status_color == "color-error"

    def test_mark_sent(self, sample_message):
        sample_message.mark_sent()
        assert sample_message.status == "sent"
        assert sample_message.sent_at is not None

    def test_mark_delivered(self, sample_message):
        sample_message.mark_delivered()
        assert sample_message.status == "delivered"
        assert sample_message.delivered_at is not None

    def test_mark_read(self, sample_message):
        sample_message.mark_read()
        assert sample_message.status == "read"
        assert sample_message.read_at is not None

    def test_mark_failed(self, sample_message):
        sample_message.mark_failed("Connection timeout")
        assert sample_message.status == "failed"
        assert sample_message.error_message == "Connection timeout"


class TestCampaign:
    def test_repr(self, sample_campaign):
        assert "Spring Sale Campaign" in repr(sample_campaign)

    def test_channel_display(self, sample_campaign):
        assert sample_campaign.channel_display == "Email"

    def test_status_display(self, sample_campaign):
        assert sample_campaign.status_display == "Draft"

    def test_status_color(self, sample_campaign):
        assert sample_campaign.status_color == ""
        sample_campaign.status = "sending"
        assert sample_campaign.status_color == "color-primary"
        sample_campaign.status = "completed"
        assert sample_campaign.status_color == "color-success"

    def test_delivery_rate_zero(self, sample_campaign):
        assert sample_campaign.delivery_rate == 0

    def test_delivery_rate_with_data(self, sample_campaign):
        sample_campaign.sent_count = 80
        sample_campaign.delivered_count = 72
        assert sample_campaign.delivery_rate == 90.0

    def test_progress_percent_zero(self, sample_campaign):
        sample_campaign.total_recipients = 0
        assert sample_campaign.progress_percent == 0

    def test_progress_percent_with_data(self, sample_campaign):
        sample_campaign.sent_count = 50
        assert sample_campaign.progress_percent == 50.0

    def test_start(self, sample_campaign):
        sample_campaign.start()
        assert sample_campaign.status == "sending"
        assert sample_campaign.started_at is not None

    def test_complete(self, sample_campaign):
        sample_campaign.complete()
        assert sample_campaign.status == "completed"
        assert sample_campaign.completed_at is not None

    def test_cancel(self, sample_campaign):
        sample_campaign.cancel()
        assert sample_campaign.status == "cancelled"


class TestMessageAutomation:
    def test_repr(self, sample_automation):
        assert "Welcome Automation" in repr(sample_automation)
        assert "welcome" in repr(sample_automation)

    def test_trigger_display(self, sample_automation):
        assert sample_automation.trigger_display == "New Customer Welcome"

    def test_channel_display(self, sample_automation):
        assert sample_automation.channel_display == "Email"

    def test_trigger_icon(self, sample_automation):
        assert sample_automation.trigger_icon == "hand-right-outline"

    def test_all_triggers_have_labels(self):
        for trigger in AUTOMATION_TRIGGER_CHOICES:
            assert trigger in AUTOMATION_TRIGGER_LABELS

    def test_all_triggers_have_icons(self):
        for trigger in AUTOMATION_TRIGGER_CHOICES:
            assert trigger in TRIGGER_ICONS


class TestChoiceLabels:
    def test_channel_labels(self):
        for ch in ("whatsapp", "sms", "email", "all"):
            assert ch in CHANNEL_LABELS

    def test_message_status_labels(self):
        for s in ("queued", "sent", "delivered", "failed", "read"):
            assert s in MESSAGE_STATUS_LABELS

    def test_campaign_status_labels(self):
        for s in ("draft", "scheduled", "sending", "completed", "cancelled"):
            assert s in CAMPAIGN_STATUS_LABELS

    def test_template_category_labels(self):
        for c in ("appointment_reminder", "booking_confirmation", "receipt", "marketing", "custom"):
            assert c in TEMPLATE_CATEGORY_LABELS
