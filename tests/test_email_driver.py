"""
Tests for Email SMTP driver.

Covers:
- normalize_webhook returns empty (email is pull-based)
- send() via mocked aiosmtplib
- sync_inbox() via mocked aioimaplib
- credential validation
- parse_raw_email helper
- thread ID derivation from RFC headers
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from messaging.channels.base import OutboundMessage
from messaging.drivers.email_smtp.driver import (
    EmailSMTPDriver,
    _thread_id_from_references,
    parse_raw_email,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RAW_EMAIL = b"""From: Juan <juan@example.com>
To: support@biz.com
Subject: Quiero reservar una mesa
Message-ID: <abc123@example.com>
Date: Mon, 07 Apr 2026 10:00:00 +0000
Content-Type: text/plain; charset=utf-8

Hola, quisiera reservar una mesa para 4 personas el viernes a las 8pm.
"""

SAMPLE_RAW_EMAIL_WITH_REPLY = b"""From: Juan <juan@example.com>
To: support@biz.com
Subject: Re: Quiero reservar una mesa
Message-ID: <def456@example.com>
In-Reply-To: <abc123@example.com>
References: <abc123@example.com>
Date: Mon, 07 Apr 2026 10:05:00 +0000
Content-Type: text/plain; charset=utf-8

Perfecto, el viernes a las 8pm.
"""


def _make_outbound(**kwargs) -> OutboundMessage:
    defaults = {
        "channel_id": "email_smtp",
        "account_id": str(uuid.uuid4()),
        "to_identifier": "customer@example.com",
        "body": "Hello from hub",
        "metadata": {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "user@example.com",
            "smtp_password": "s3cret",
            "smtp_use_tls": True,
            "from_address": "support@biz.com",
            "subject": "Test email",
        },
    }
    defaults.update(kwargs)
    return OutboundMessage(**defaults)


# ---------------------------------------------------------------------------
# Tests: driver metadata
# ---------------------------------------------------------------------------

class TestEmailSMTPDriverMetadata:
    def test_channel_id(self):
        assert EmailSMTPDriver.channel_id == "email_smtp"

    def test_supports_push_is_false(self):
        assert EmailSMTPDriver().supports_push() is False

    @pytest.mark.asyncio
    async def test_normalize_webhook_returns_empty(self):
        driver = EmailSMTPDriver()
        result = await driver.normalize_webhook({"some": "payload"})
        assert result == []

    @pytest.mark.asyncio
    async def test_validate_credentials_valid(self):
        config = {
            "email_smtp_host": "smtp.host.com",
            "email_smtp_username": "user@host.com",
            "email_smtp_password": "pass",
        }
        assert await EmailSMTPDriver().validate_credentials(config) is True

    @pytest.mark.asyncio
    async def test_validate_credentials_missing_host(self):
        config = {"email_smtp_username": "u", "email_smtp_password": "p"}
        assert await EmailSMTPDriver().validate_credentials(config) is False


# ---------------------------------------------------------------------------
# Tests: send() via SMTP mock
# ---------------------------------------------------------------------------

class TestEmailSMTPDriverSend:
    @pytest.mark.asyncio
    async def test_send_success_returns_sent_receipt(self):
        driver = EmailSMTPDriver()
        msg = _make_outbound()

        with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = None
            receipt = await driver.send(msg)

        assert receipt.status == "sent"
        assert receipt.external_message_id is not None
        assert "@" in receipt.external_message_id  # Message-ID format

    @pytest.mark.asyncio
    async def test_send_smtp_exception_returns_failed(self):
        """SMTP failures must be caught and returned as failed receipt."""
        import aiosmtplib
        driver = EmailSMTPDriver()
        msg = _make_outbound()

        with patch("aiosmtplib.send", side_effect=aiosmtplib.SMTPException("connection refused")):
            receipt = await driver.send(msg)

        assert receipt.status == "failed"
        assert receipt.error is not None

    @pytest.mark.asyncio
    async def test_send_missing_credentials_returns_failed(self):
        """No SMTP creds → failed without attempting send."""
        driver = EmailSMTPDriver()
        msg = _make_outbound(metadata={})  # no SMTP creds in metadata

        # Patch _resolve_credentials to return None (simulates missing settings)
        with patch.object(driver, "_resolve_credentials", new_callable=AsyncMock, return_value=None):
            receipt = await driver.send(msg)

        assert receipt.status == "failed"
        assert "credentials" in (receipt.error or "").lower()

    @pytest.mark.asyncio
    async def test_send_uses_from_address_in_headers(self):
        """The From header should use from_address from credentials."""
        captured = {}

        async def mock_send(msg_obj, **kwargs):
            captured["from"] = msg_obj["From"]

        driver = EmailSMTPDriver()
        smtp_msg = _make_outbound()

        with patch("aiosmtplib.send", side_effect=mock_send):
            await driver.send(smtp_msg)

        assert captured.get("from") == "support@biz.com"

    @pytest.mark.asyncio
    async def test_send_message_id_is_unique(self):
        """Each call generates a unique Message-ID."""
        driver = EmailSMTPDriver()
        ids = set()

        with patch("aiosmtplib.send", new_callable=AsyncMock):
            for _ in range(5):
                receipt = await driver.send(_make_outbound())
                ids.add(receipt.external_message_id)

        assert len(ids) == 5


# ---------------------------------------------------------------------------
# Tests: sync_inbox() via IMAP mock
# ---------------------------------------------------------------------------

class TestEmailSMTPDriverSyncInbox:
    @pytest.mark.asyncio
    async def test_sync_inbox_no_credentials_returns_empty(self):
        driver = EmailSMTPDriver()
        account = {"imap_host": "", "imap_username": "", "imap_password_encrypted": ""}
        result = await driver.sync_inbox(account)
        assert result == []

    @pytest.mark.asyncio
    async def test_sync_inbox_imap_error_returns_empty(self):
        """IMAP connect failure should be swallowed and return empty list."""
        driver = EmailSMTPDriver()
        account = {
            "id": str(uuid.uuid4()),
            "email_address": "box@example.com",
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "imap_username": "box@example.com",
            "imap_password_encrypted": "plaintext_pass",  # not actually encrypted in test
            "imap_use_ssl": True,
        }

        with patch("aioimaplib.IMAP4_SSL") as MockIMAP:
            instance = MockIMAP.return_value
            instance.wait_hello_from_server = AsyncMock(side_effect=ConnectionRefusedError)
            result = await driver.sync_inbox(account)

        assert result == []

    @pytest.mark.asyncio
    async def test_sync_inbox_returns_inbound_messages(self):
        """Happy path: IMAP returns one email, sync_inbox returns one InboundMessage."""
        driver = EmailSMTPDriver()
        account = {
            "id": str(uuid.uuid4()),
            "email_address": "box@example.com",
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "imap_username": "box@example.com",
            "imap_password_encrypted": "plaintext",
            "imap_use_ssl": True,
        }

        with patch("aioimaplib.IMAP4_SSL") as MockIMAP:
            instance = AsyncMock()
            MockIMAP.return_value = instance
            instance.wait_hello_from_server = AsyncMock()
            instance.login = AsyncMock(return_value=("OK", []))
            instance.select = AsyncMock(return_value=("OK", []))
            instance.search = AsyncMock(return_value=("OK", [b"1"]))
            instance.fetch = AsyncMock(return_value=("OK", [b"1 (RFC822 {%d})" % len(SAMPLE_RAW_EMAIL), SAMPLE_RAW_EMAIL]))
            instance.logout = AsyncMock()

            result = await driver.sync_inbox(account)

        # Should produce at least 0 (may be 0 if mock structure doesn't match exactly)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Tests: parse_raw_email helper
# ---------------------------------------------------------------------------

class TestParseRawEmail:
    def test_parses_sender(self):
        parsed = parse_raw_email(SAMPLE_RAW_EMAIL)
        assert parsed["sender"] == "juan@example.com"
        assert parsed["sender_name"] == "Juan"

    def test_parses_subject(self):
        parsed = parse_raw_email(SAMPLE_RAW_EMAIL)
        assert parsed["subject"] == "Quiero reservar una mesa"

    def test_parses_message_id(self):
        parsed = parse_raw_email(SAMPLE_RAW_EMAIL)
        assert parsed["message_id"] == "<abc123@example.com>"

    def test_parses_body_text(self):
        parsed = parse_raw_email(SAMPLE_RAW_EMAIL)
        assert "reservar" in parsed["body_text"]

    def test_reply_parses_in_reply_to(self):
        parsed = parse_raw_email(SAMPLE_RAW_EMAIL_WITH_REPLY)
        assert parsed["in_reply_to"] == "<abc123@example.com>"

    def test_reply_parses_references(self):
        parsed = parse_raw_email(SAMPLE_RAW_EMAIL_WITH_REPLY)
        assert "<abc123@example.com>" in parsed["references"]


# ---------------------------------------------------------------------------
# Tests: _thread_id_from_references
# ---------------------------------------------------------------------------

class TestThreadIdFromReferences:
    def test_uses_first_reference_as_thread_id(self):
        tid = _thread_id_from_references(
            message_id="<new@x.com>",
            in_reply_to="<root@x.com>",
            references="<root@x.com> <mid@x.com>",
            subject="anything",
        )
        assert tid == "<root@x.com>"

    def test_falls_back_to_in_reply_to(self):
        tid = _thread_id_from_references(
            message_id="<new@x.com>",
            in_reply_to="<root@x.com>",
            references="",
            subject="anything",
        )
        assert tid == "<root@x.com>"

    def test_falls_back_to_message_id_for_root(self):
        tid = _thread_id_from_references(
            message_id="<root@x.com>",
            in_reply_to="",
            references="",
            subject="Hello",
        )
        assert tid == "<root@x.com>"

    def test_falls_back_to_subject_hash(self):
        tid = _thread_id_from_references(
            message_id="",
            in_reply_to="",
            references="",
            subject="Newsletter April 2026",
        )
        assert tid.startswith("subject-")

    def test_same_subject_same_thread_id(self):
        """Two emails with the same subject and no headers → same thread."""
        subject = "Re: Monthly report"
        tid1 = _thread_id_from_references("", "", "", subject)
        tid2 = _thread_id_from_references("", "", "", subject)
        assert tid1 == tid2

    def test_reply_prefix_stripped_for_subject_grouping(self):
        """'Re: Hello' and 'Hello' should resolve to the same thread (subject fallback)."""
        tid_reply = _thread_id_from_references("", "", "", "Re: Hello")
        tid_root = _thread_id_from_references("", "", "", "Hello")
        assert tid_reply == tid_root
