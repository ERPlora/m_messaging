"""
Central webhook router for all messaging channels.

Mounted at /webhooks/messaging/{channel_id}/{account_id}.

GET  /webhooks/messaging/{channel_id}/{account_id} — webhook verification
POST /webhooks/messaging/{channel_id}/{account_id} — inbound message processing

Each channel driver handles its own verification and payload normalization.
After normalization, the router upserts Conversation + Message records and
emits the "messaging.inbound_received" event via the EventBus.

This router is registered in modules/messaging/routes.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from ..channels.registry import get_driver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/messaging", tags=["messaging-webhooks"])


# ---------------------------------------------------------------------------
# GET — webhook verification
# ---------------------------------------------------------------------------

@router.get("/{channel_id}/{account_id}")
async def verify_webhook(
    channel_id: str,
    account_id: str,
    request: Request,
) -> PlainTextResponse:
    """Handle webhook verification (e.g. Meta hub.challenge handshake)."""
    driver = get_driver(channel_id)
    if driver is None:
        logger.warning("[WebhookRouter] Unknown channel: %s", channel_id)
        return PlainTextResponse("Unknown channel", status_code=404)

    # WhatsApp uses a specific verification flow
    if channel_id == "whatsapp":
        from ..drivers.whatsapp_business.webhook import verify_webhook as _wa_verify
        return await _wa_verify(request, account_id)

    # Generic fallback: return 200 for any GET (non-WhatsApp channels)
    return PlainTextResponse("OK", status_code=200)


# ---------------------------------------------------------------------------
# POST — inbound message processing
# ---------------------------------------------------------------------------

@router.post("/{channel_id}/{account_id}")
async def receive_webhook(
    channel_id: str,
    account_id: str,
    request: Request,
) -> JSONResponse:
    """Process an inbound webhook payload from a messaging channel."""
    driver = get_driver(channel_id)
    if driver is None:
        logger.warning("[WebhookRouter] Unknown channel: %s", channel_id)
        return JSONResponse({"error": f"Unknown channel: {channel_id}"}, status_code=404)

    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        logger.warning("[WebhookRouter] Could not parse JSON for channel=%s", channel_id)
        payload = {}

    headers = dict(request.headers)

    # Normalize webhook → list[InboundMessage]
    try:
        messages = await driver.normalize_webhook(payload, headers)
    except Exception:
        logger.exception(
            "[WebhookRouter] normalize_webhook failed for channel=%s account=%s",
            channel_id,
            account_id,
        )
        return JSONResponse({"error": "Internal error processing webhook"}, status_code=500)

    if not messages:
        # Meta requires 200 even for status updates / empty payloads
        return JSONResponse({"status": "ok", "processed": 0})

    # Persist conversations + messages
    processed = 0
    for inbound in messages:
        try:
            await _persist_inbound(inbound)
            processed += 1
        except Exception:
            logger.exception(
                "[WebhookRouter] Failed to persist inbound message external_id=%s",
                inbound.external_message_id,
            )

    # Emit event for downstream hooks
    try:
        from app.core.events import emit  # type: ignore[import]
        await emit("messaging.inbound_received", {
            "channel_id": channel_id,
            "account_id": account_id,
            "count": processed,
        })
    except Exception:
        logger.debug("[WebhookRouter] EventBus not available, skipping emit")

    return JSONResponse({"status": "ok", "processed": processed})


# ---------------------------------------------------------------------------
# Persistence helper
# ---------------------------------------------------------------------------

async def _persist_inbound(inbound) -> None:
    """Upsert a Conversation and Message for an InboundMessage.

    Uses the communications module's Thread+Message models if available,
    otherwise silently no-ops (data flows through existing whatsapp_inbox tables
    until migration is complete).

    Idempotency: Message is skipped if external_message_id already exists.
    """
    try:
        from communications.models import (  # type: ignore[import]
            CommunicationAccount,
            Message,
            Thread,
        )
        from app.core.db.session import get_async_session
        from sqlalchemy import select

        async with get_async_session() as db:
            # Look up account (CommunicationAccount) by channel + external_account_id
            account = await db.execute(
                select(CommunicationAccount).where(
                    CommunicationAccount.external_account_id == inbound.account_id,
                    CommunicationAccount.channel == inbound.channel_id,
                    CommunicationAccount.is_deleted.is_(False),
                )
            )
            account = account.scalar_one_or_none()

            if account is None:
                logger.debug(
                    "[WebhookRouter] No CommunicationAccount for channel=%s account_id=%s — skipping persist",
                    inbound.channel_id,
                    inbound.account_id,
                )
                return

            # Idempotency: skip if message already persisted
            existing = await db.execute(
                select(Message).where(
                    Message.external_id == inbound.external_message_id,
                    Message.hub_id == account.hub_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                logger.debug(
                    "[WebhookRouter] Duplicate message external_id=%s — skipping",
                    inbound.external_message_id,
                )
                return

            # Upsert Thread (conversation)
            thread = await db.execute(
                select(Thread).where(
                    Thread.hub_id == account.hub_id,
                    Thread.account_id == account.id,
                    Thread.contact_identifier == inbound.external_thread_id,
                    Thread.is_deleted.is_(False),
                )
            )
            thread = thread.scalar_one_or_none()

            now = datetime.now(UTC)

            if thread is None:
                sender_name = inbound.metadata.get("sender_name", inbound.from_identifier)
                subject = inbound.metadata.get("subject", "")
                thread = Thread(
                    hub_id=account.hub_id,
                    account_id=account.id,
                    channel=inbound.channel_id,
                    contact_identifier=inbound.external_thread_id,
                    contact_name=sender_name,
                    subject=subject,
                    status="open",
                    last_message_at=now,
                    unread_count=1,
                    message_count=1,
                )
                db.add(thread)
                await db.flush()
            else:
                thread.last_message_at = now
                thread.unread_count = (thread.unread_count or 0) + 1
                thread.message_count = (thread.message_count or 0) + 1

            # Create Message
            body = inbound.body or ""
            msg = Message(
                hub_id=account.hub_id,
                thread_id=thread.id,
                direction="inbound",
                sender_address=inbound.from_identifier,
                sender_name=inbound.metadata.get("sender_name", inbound.from_identifier),
                body_text=body,
                subject=inbound.metadata.get("subject", ""),
                status="received",
                external_id=inbound.external_message_id,
                message_id_header=inbound.metadata.get("in_reply_to", ""),
            )
            db.add(msg)
            await db.flush()

    except ImportError:
        logger.debug("[WebhookRouter] communications module not available — skipping DB persist")
    except Exception:
        logger.exception("[WebhookRouter] Error persisting inbound message")
        raise
