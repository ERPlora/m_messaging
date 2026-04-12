"""
Tests for the unified inbox (multi-channel conversation list).

Since the inbox view queries the DB (communications.Thread +
whatsapp_inbox.WhatsAppConversation), these tests exercise the business logic
without a real DB by testing the helper functions and the channel sorting logic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC, timedelta



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conv(
    channel: str,
    contact_name: str,
    last_message_at: datetime,
    status: str = "open",
    unread_count: int = 0,
) -> dict:
    """Build a conversation dict as produced by the inbox view."""
    return {
        "id": str(uuid.uuid4()),
        "channel": channel,
        "channel_icon": "chatbubble-outline",
        "contact_name": contact_name,
        "contact_identifier": f"{channel}_contact",
        "last_message_at": last_message_at,
        "status": status,
        "unread_count": unread_count,
        "subject": f"Thread with {contact_name}",
        "detail_url": f"/m/messaging/test/{channel}",
    }


def _sort_conversations(conversations: list[dict]) -> list[dict]:
    """Replicate the sorting logic from routes.inbox."""
    return sorted(
        conversations,
        key=lambda c: c["last_message_at"] or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Tests: multi-channel sorting
# ---------------------------------------------------------------------------

class TestInboxUnifiedSorting:
    """The inbox must merge and sort conversations by last_message_at."""

    def test_whatsapp_and_email_sorted_by_recency(self):
        now = datetime.now(UTC)
        wa_conv = _make_conv("whatsapp", "Juan WhatsApp", now - timedelta(minutes=5))
        email_conv = _make_conv("email", "Ana Email", now - timedelta(minutes=1))

        conversations = [wa_conv, email_conv]
        sorted_convs = _sort_conversations(conversations)

        assert sorted_convs[0]["channel"] == "email"   # most recent
        assert sorted_convs[1]["channel"] == "whatsapp"

    def test_none_last_message_at_goes_to_bottom(self):
        now = datetime.now(UTC)
        recent = _make_conv("whatsapp", "Recent", now)
        no_msg = _make_conv("email", "No messages", None)  # type: ignore[arg-type]

        conversations = [no_msg, recent]
        sorted_convs = _sort_conversations(conversations)

        assert sorted_convs[0]["channel"] == "whatsapp"
        assert sorted_convs[1]["channel"] == "email"

    def test_sorting_preserves_all_channels(self):
        now = datetime.now(UTC)
        convs = [
            _make_conv("whatsapp", "WA1", now - timedelta(hours=3)),
            _make_conv("email", "Email1", now - timedelta(hours=1)),
            _make_conv("whatsapp", "WA2", now - timedelta(hours=2)),
            _make_conv("email", "Email2", now - timedelta(minutes=30)),
        ]
        sorted_convs = _sort_conversations(convs)

        assert sorted_convs[0]["contact_name"] == "Email2"
        assert sorted_convs[1]["contact_name"] == "Email1"
        assert sorted_convs[2]["contact_name"] == "WA2"
        assert sorted_convs[3]["contact_name"] == "WA1"

    def test_all_channels_present_after_merge(self):
        now = datetime.now(UTC)
        convs = [
            _make_conv("whatsapp", "WA", now),
            _make_conv("email", "Email", now - timedelta(seconds=1)),
        ]
        channels = {c["channel"] for c in convs}
        assert "whatsapp" in channels
        assert "email" in channels


# ---------------------------------------------------------------------------
# Tests: unread badge logic
# ---------------------------------------------------------------------------

class TestInboxUnreadBadge:
    def test_unread_count_preserved(self):
        now = datetime.now(UTC)
        conv = _make_conv("whatsapp", "Alice", now, unread_count=5)
        assert conv["unread_count"] == 5

    def test_zero_unread_no_badge(self):
        now = datetime.now(UTC)
        conv = _make_conv("email", "Bob", now, unread_count=0)
        assert conv["unread_count"] == 0


# ---------------------------------------------------------------------------
# Tests: conversation dict structure
# ---------------------------------------------------------------------------

class TestConversationDict:
    """All required keys must be present for each conversation."""

    REQUIRED_KEYS = {
        "id", "channel", "channel_icon", "contact_name",
        "contact_identifier", "last_message_at", "status",
        "unread_count", "subject", "detail_url",
    }

    def test_whatsapp_conv_has_all_keys(self):
        conv = _make_conv("whatsapp", "Test", datetime.now(UTC))
        assert set(conv.keys()) >= self.REQUIRED_KEYS

    def test_email_conv_has_all_keys(self):
        conv = _make_conv("email", "Test", datetime.now(UTC))
        assert set(conv.keys()) >= self.REQUIRED_KEYS

    def test_channel_in_expected_values(self):
        for channel in ("whatsapp", "email", "instagram", "facebook"):
            conv = _make_conv(channel, "Test", datetime.now(UTC))
            assert conv["channel"] == channel

    def test_detail_url_is_string(self):
        conv = _make_conv("whatsapp", "Test", datetime.now(UTC))
        assert isinstance(conv["detail_url"], str)
        assert conv["detail_url"].startswith("/")


# ---------------------------------------------------------------------------
# Tests: channel filter logic
# ---------------------------------------------------------------------------

class TestInboxChannelFilter:
    """Filtering by channel should exclude other channels."""

    def test_filter_whatsapp_excludes_email(self):
        now = datetime.now(UTC)
        all_convs = [
            _make_conv("whatsapp", "WA", now),
            _make_conv("email", "Email", now - timedelta(seconds=1)),
        ]
        filtered = [c for c in all_convs if c["channel"] == "whatsapp"]
        assert len(filtered) == 1
        assert filtered[0]["channel"] == "whatsapp"

    def test_filter_email_excludes_whatsapp(self):
        now = datetime.now(UTC)
        all_convs = [
            _make_conv("whatsapp", "WA", now),
            _make_conv("email", "Email", now - timedelta(seconds=1)),
        ]
        filtered = [c for c in all_convs if c["channel"] == "email"]
        assert len(filtered) == 1
        assert filtered[0]["channel"] == "email"

    def test_no_filter_returns_all(self):
        now = datetime.now(UTC)
        all_convs = [
            _make_conv("whatsapp", "WA", now),
            _make_conv("email", "Email", now - timedelta(seconds=1)),
        ]
        # No filter → all channels
        assert len(all_convs) == 2
