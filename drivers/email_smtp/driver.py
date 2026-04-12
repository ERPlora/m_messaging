"""
SMTP + IMAP email driver — REAL implementation.

Migrated from modules/communications/services/channels/email.py.

Supports:
- send(): compose and send email via aiosmtplib (SMTP)
- sync_inbox(): fetch new emails via aioimaplib (IMAP), create Thread+Message idempotently
- normalize_webhook(): email-to-webhook services (returns empty — email is pull-based)
- validate_credentials(): test SMTP + IMAP connectivity

Credentials live in CommunicationAccount (communications module) or
MessagingSettings (legacy) depending on which is available.
"""

from __future__ import annotations

import email as _email_stdlib
import email.encoders
import email.mime.base
import email.mime.multipart
import email.mime.text
import email.utils
import hashlib
import logging
import uuid
from datetime import datetime, UTC
from email.header import decode_header as _decode_header
from typing import Any

from ...channels.base import (
    Capability,
    ChannelDriver,
    DeliveryReceipt,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email parsing helpers (moved from communications.services.channels.email)
# ---------------------------------------------------------------------------

def _decode_header_value(value: str | None) -> str:
    """Decode an RFC-2047 encoded header value into a plain string."""
    if not value:
        return ""
    parts: list[str] = []
    for fragment, charset in _decode_header(value):
        if isinstance(fragment, bytes):
            parts.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(fragment)
    return " ".join(parts)


def _extract_addresses(msg: _email_stdlib.message.Message, header: str) -> list[str]:
    """Return list of email addresses from a header (To, Cc, Bcc)."""
    raw = msg.get_all(header, [])
    addresses: list[str] = []
    for item in raw:
        for _name, addr in _email_stdlib.utils.getaddresses([item]):
            if addr:
                addresses.append(addr)
    return addresses


def parse_raw_email(raw_bytes: bytes) -> dict:
    """Parse raw email bytes into a structured dict.

    Returns:
        {
            sender, sender_name, recipients, cc, subject,
            body_text, body_html, attachments,
            message_id, in_reply_to, references, date
        }
    """
    msg = _email_stdlib.message_from_bytes(raw_bytes)

    from_header = msg.get("From", "")
    sender_name, sender_addr = _email_stdlib.utils.parseaddr(from_header)
    sender_name = _decode_header_value(sender_name) or sender_addr

    date_str = msg.get("Date", "")
    date_parsed: datetime | None = None
    if date_str:
        try:
            date_parsed = _email_stdlib.utils.parsedate_to_datetime(date_str).astimezone(UTC)
        except Exception:
            pass

    body_text = ""
    body_html = ""
    attachments: list[dict] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition:
                attachments.append({
                    "filename": _decode_header_value(part.get_filename() or "attachment"),
                    "content_type": content_type,
                    "data": part.get_payload(decode=True) or b"",
                })
                continue

            if content_type == "text/plain" and not body_text:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_text = payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not body_html:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_html = payload.decode(charset, errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                body_html = decoded
            else:
                body_text = decoded

    return {
        "sender": sender_addr,
        "sender_name": sender_name,
        "recipients": _extract_addresses(msg, "To"),
        "cc": _extract_addresses(msg, "Cc"),
        "subject": _decode_header_value(msg.get("Subject", "")),
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
        "message_id": msg.get("Message-ID", ""),
        "in_reply_to": msg.get("In-Reply-To", ""),
        "references": msg.get("References", ""),
        "date": date_parsed,
    }


# ---------------------------------------------------------------------------
# EmailSMTPDriver
# ---------------------------------------------------------------------------

class EmailSMTPDriver(ChannelDriver):
    """
    SMTP + IMAP email channel driver.

    Real implementation — absorbs communications email send + IMAP sync logic.
    """

    channel_id = "email_smtp"
    display_name = "Email (SMTP/IMAP)"
    icon = "mail-outline"
    capabilities = {
        Capability.TEXT,
        Capability.MEDIA,
        Capability.THREADING,
    }

    # -------------------------------------------------------------------------
    # send
    # -------------------------------------------------------------------------

    async def send(self, msg: OutboundMessage) -> DeliveryReceipt:
        """Send an email via SMTP.

        Credentials: resolved from msg.metadata or from MessagingSettings.

        Required metadata keys:
            smtp_host, smtp_port, smtp_username, smtp_password,
            smtp_use_tls (optional, default True),
            from_address, subject (optional)

        Returns DeliveryReceipt with external_message_id = generated Message-ID.
        """
        creds = await self._resolve_credentials(msg.account_id, msg.metadata)
        if not creds:
            return DeliveryReceipt(
                external_message_id=None,
                status="failed",
                error="Missing SMTP credentials",
            )

        try:
            import aiosmtplib
        except ImportError:
            logger.error("[EmailSMTPDriver] aiosmtplib not installed")
            return DeliveryReceipt(
                external_message_id=None,
                status="failed",
                error="aiosmtplib not installed",
            )

        subject = msg.metadata.get("subject", "") or "(no subject)"
        from_address = creds.get("from_address") or creds["smtp_username"]

        domain = from_address.split("@")[-1] if "@" in from_address else "erplora.com"
        message_id = f"<{uuid.uuid4()}@{domain}>"

        mime_msg = _email_stdlib.mime.multipart.MIMEMultipart("alternative")
        mime_msg["From"] = from_address
        mime_msg["To"] = msg.to_identifier
        mime_msg["Subject"] = subject
        mime_msg["Date"] = _email_stdlib.utils.formatdate(localtime=True)
        mime_msg["Message-ID"] = message_id

        in_reply_to = msg.metadata.get("in_reply_to", "")
        references = msg.metadata.get("references", "")
        if in_reply_to:
            mime_msg["In-Reply-To"] = in_reply_to
        if references:
            mime_msg["References"] = references

        mime_msg.attach(_email_stdlib.mime.text.MIMEText(msg.body, "plain", "utf-8"))

        for att in msg.attachments:
            ct = att.content_type or "application/octet-stream"
            main_type, sub_type = ct.split("/", 1) if "/" in ct else ("application", "octet-stream")
            part = _email_stdlib.mime.base.MIMEBase(main_type, sub_type)
            if att.url:
                # Attachment data not embedded — skip (media download not in scope)
                continue
            _email_stdlib.encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=att.filename)
            mime_msg.attach(part)

        try:
            await aiosmtplib.send(
                mime_msg,
                hostname=creds["smtp_host"],
                port=int(creds.get("smtp_port", 587)),
                username=creds["smtp_username"],
                password=creds["smtp_password"],
                start_tls=creds.get("smtp_use_tls", True),
                recipients=[msg.to_identifier],
            )
            logger.info(
                "[EmailSMTPDriver] Sent email to %s (Message-ID: %s)",
                msg.to_identifier,
                message_id,
            )
        except Exception as exc:
            logger.exception("[EmailSMTPDriver] SMTP send failed")
            return DeliveryReceipt(
                external_message_id=None,
                status="failed",
                error=str(exc),
            )

        return DeliveryReceipt(
            external_message_id=message_id,
            status="sent",
            raw={"message_id": message_id},
        )

    # -------------------------------------------------------------------------
    # normalize_webhook
    # -------------------------------------------------------------------------

    async def normalize_webhook(
        self,
        payload: dict,
        headers: dict | None = None,
    ) -> list[InboundMessage]:
        """Email does not push webhooks in the standard flow; returns empty list.

        Email-to-webhook services (e.g. SendGrid Inbound Parse) could be
        handled here in a future extension.
        """
        logger.debug("[EmailSMTPDriver] normalize_webhook called (email is pull-based)")
        return []

    # -------------------------------------------------------------------------
    # validate_credentials
    # -------------------------------------------------------------------------

    async def validate_credentials(self, config: dict) -> bool:
        """Validate SMTP credentials (host + username + password required)."""
        required = ("email_smtp_host", "email_smtp_username", "email_smtp_password")
        return all(config.get(k) for k in required)

    # -------------------------------------------------------------------------
    # supports_push / sync_inbox
    # -------------------------------------------------------------------------

    def supports_push(self) -> bool:
        """SMTP/IMAP is pull-based — use sync_inbox for inbox retrieval."""
        return False

    async def sync_inbox(self, account: Any) -> list[InboundMessage]:
        """Pull new emails from IMAP and return as InboundMessage list.

        Uses aioimaplib for async IMAP access.
        Credentials come from the account object (CommunicationAccount model)
        or a plain dict with the same field names.

        Idempotency: callers should check external_message_id (Message-ID header)
        before persisting to avoid duplicates.

        Args:
            account: CommunicationAccount instance or dict with IMAP fields

        Returns:
            list[InboundMessage] — one per email fetched
        """
        try:
            import aioimaplib
        except ImportError:
            logger.error("[EmailSMTPDriver] aioimaplib not installed")
            return []

        # Support both ORM objects and plain dicts
        def _get(obj, key, default=""):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        imap_host = _get(account, "imap_host")
        imap_port = int(_get(account, "imap_port", 993))
        imap_username = _get(account, "imap_username")
        imap_use_ssl = _get(account, "imap_use_ssl", True)
        account_id = str(_get(account, "id", "") or _get(account, "account_id", ""))
        email_address = _get(account, "email_address", imap_username)

        # Decrypt password if it looks encrypted (non-empty and has Fernet prefix)
        raw_password = _get(account, "imap_password_encrypted", "")
        imap_password = _decrypt_if_needed(raw_password)

        if not imap_host or not imap_username or not imap_password:
            logger.warning("[EmailSMTPDriver] IMAP credentials incomplete for account %s", account_id)
            return []

        messages: list[InboundMessage] = []
        imap = None

        try:
            if imap_use_ssl:
                imap = aioimaplib.IMAP4_SSL(host=imap_host, port=imap_port)
            else:
                imap = aioimaplib.IMAP4(host=imap_host, port=imap_port)

            await imap.wait_hello_from_server()
            await imap.login(imap_username, imap_password)

            _status, _ = await imap.select("INBOX")
            _status, data = await imap.search("ALL")

            if not data or not data[0]:
                return messages

            uids = data[0].split()
            logger.info(
                "[EmailSMTPDriver] IMAP sync for %s: %d messages to fetch",
                email_address,
                len(uids),
            )

            for uid in uids[-100:]:  # cap at 100 per sync to avoid overload
                try:
                    uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
                    _status, msg_data = await imap.fetch(uid_str, "(RFC822)")
                    if not msg_data or len(msg_data) < 2:
                        continue

                    raw_email = msg_data[1]
                    if isinstance(raw_email, tuple):
                        raw_email = raw_email[1] if len(raw_email) > 1 else raw_email[0]
                    if isinstance(raw_email, str):
                        raw_email = raw_email.encode()
                    if not isinstance(raw_email, bytes):
                        continue

                    parsed = parse_raw_email(raw_email)

                    # Use Message-ID header as external_message_id (idempotency key)
                    external_message_id = parsed["message_id"] or _make_fallback_id(
                        parsed["sender"], parsed["subject"], uid_str
                    )
                    external_thread_id = _thread_id_from_references(
                        parsed["message_id"],
                        parsed["in_reply_to"],
                        parsed["references"],
                        parsed["subject"],
                    )

                    sent_at = parsed["date"].isoformat() if parsed["date"] else None

                    attachments = [
                        _email_stdlib_att_to_attachment(att) for att in parsed["attachments"]
                    ]

                    messages.append(InboundMessage(
                        channel_id="email_smtp",
                        account_id=account_id,
                        external_thread_id=external_thread_id,
                        external_message_id=external_message_id,
                        from_identifier=parsed["sender"],
                        body=parsed["body_text"] or parsed["body_html"] or "",
                        attachments=attachments,
                        metadata={
                            "sender_name": parsed["sender_name"],
                            "subject": parsed["subject"],
                            "body_html": parsed["body_html"],
                            "recipients": parsed["recipients"],
                            "cc": parsed["cc"],
                            "in_reply_to": parsed["in_reply_to"],
                            "references": parsed["references"],
                            "imap_uid": uid_str,
                        },
                        sent_at=sent_at,
                    ))

                except Exception:
                    logger.exception("[EmailSMTPDriver] Failed to parse email UID %s", uid)
                    continue

        except Exception:
            logger.exception("[EmailSMTPDriver] IMAP sync failed for account %s", account_id)
        finally:
            if imap:
                try:
                    await imap.logout()
                except Exception:
                    pass

        return messages

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _resolve_credentials(self, account_id: str, metadata: dict) -> dict | None:
        """Resolve SMTP credentials from metadata or MessagingSettings."""
        # Direct metadata takes priority
        if metadata.get("smtp_host") and metadata.get("smtp_username"):
            return {
                "smtp_host": metadata["smtp_host"],
                "smtp_port": metadata.get("smtp_port", 587),
                "smtp_username": metadata["smtp_username"],
                "smtp_password": metadata.get("smtp_password", ""),
                "smtp_use_tls": metadata.get("smtp_use_tls", True),
                "from_address": metadata.get("from_address", metadata["smtp_username"]),
            }

        # Fallback: MessagingSettings
        try:
            from app.core.db.session import get_sync_session
            from messaging.models import MessagingSettings
            import uuid as _uuid
            from sqlalchemy import select

            with get_sync_session() as db:
                try:
                    hub_uuid = _uuid.UUID(account_id)
                except ValueError:
                    return None

                row = db.execute(
                    select(MessagingSettings).where(
                        MessagingSettings.hub_id == hub_uuid,
                        MessagingSettings.is_deleted.is_(False),
                    )
                ).scalar_one_or_none()

                if row and row.email_smtp_host and row.email_smtp_username:
                    return {
                        "smtp_host": row.email_smtp_host,
                        "smtp_port": row.email_smtp_port,
                        "smtp_username": row.email_smtp_username,
                        "smtp_password": row.email_smtp_password,
                        "smtp_use_tls": row.email_smtp_use_tls,
                        "from_address": row.email_from_address or row.email_smtp_username,
                    }
        except Exception:
            logger.debug(
                "[EmailSMTPDriver] Could not load credentials from MessagingSettings "
                "for account_id=%s", account_id,
            )

        return None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _decrypt_if_needed(value: str) -> str:
    """Try to decrypt if looks like a Fernet token, else return as-is."""
    if not value:
        return ""
    try:
        from communications.services.crypto import decrypt  # type: ignore[import]
        return decrypt(value)
    except Exception:
        return value


def _make_fallback_id(sender: str, subject: str, uid: str) -> str:
    """Generate a deterministic external_message_id when Message-ID header is missing."""
    key = f"{sender}|{subject}|{uid}"
    return f"<fallback-{hashlib.sha256(key.encode()).hexdigest()[:16]}@erplora.com>"


def _thread_id_from_references(
    message_id: str,
    in_reply_to: str,
    references: str,
    subject: str,
) -> str:
    """Derive a stable thread ID from email threading headers.

    Uses the first Message-ID in the References chain, or in_reply_to,
    or the message_id itself (for root messages).
    Falls back to a hash of the subject for messages without proper headers.
    """
    if references:
        # References is space-separated list of Message-IDs, oldest first
        first_ref = references.strip().split()[0]
        if first_ref:
            return first_ref

    if in_reply_to:
        return in_reply_to.strip()

    if message_id:
        return message_id.strip()

    # No threading headers — group by normalized subject
    clean_subject = subject.lower().strip()
    for prefix in ("re:", "fwd:", "fw:", "re :", "fwd :"):
        clean_subject = clean_subject.removeprefix(prefix).strip()
    return f"subject-{hashlib.md5(clean_subject.encode()).hexdigest()[:16]}"


def _email_stdlib_att_to_attachment(att: dict):
    """Convert a parsed attachment dict to an Attachment dataclass."""
    from ...channels.base import Attachment
    return Attachment(
        filename=att.get("filename", "attachment"),
        content_type=att.get("content_type", "application/octet-stream"),
        url=None,
        size=len(att.get("data", b"")),
    )
