"""
Messaging module REST API -- FastAPI router.

JSON endpoints for programmatic sending and delivery webhooks.
Mounted at /api/v1/m/messaging/ by ModuleRuntime.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.db.query import HubQuery
from app.core.db.transactions import atomic
from app.core.dependencies import CurrentUser, DbSession, HubId

from .models import Message


api_router = APIRouter()


def _q(model, session, hub_id):
    return HubQuery(model, session, hub_id)


@api_router.post("/send")
async def api_send(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """API endpoint to send a message programmatically from other modules."""
    body = await request.json()

    channel = body.get("channel")
    recipient_contact = body.get("recipient_contact", "")
    msg_body = body.get("body", "")
    recipient_name = body.get("recipient_name", "")
    subject = body.get("subject", "")
    template_id = body.get("template_id")
    customer_id = body.get("customer_id")
    extra_metadata = body.get("extra_metadata", {})

    if not channel or not recipient_contact or not msg_body:
        return JSONResponse(
            {"success": False, "error": "channel, recipient_contact, and body are required"},
            status_code=400,
        )

    if channel not in ("whatsapp", "sms", "email"):
        return JSONResponse(
            {"success": False, "error": "Invalid channel. Must be whatsapp, sms, or email"},
            status_code=400,
        )

    async with atomic(db) as session:
        msg = Message(
            hub_id=hub_id,
            channel=channel,
            recipient_name=recipient_name,
            recipient_contact=recipient_contact,
            subject=subject,
            body=msg_body,
            status="queued",
            template_id=uuid.UUID(template_id) if template_id else None,
            customer_id=uuid.UUID(customer_id) if customer_id else None,
            extra_metadata=extra_metadata,
        )
        session.add(msg)
        await session.flush()
        # In production this would queue for async sending
        msg.mark_sent()

    return JSONResponse({
        "success": True,
        "message_id": str(msg.id),
        "status": msg.status,
    })


@api_router.post("/webhook")
async def api_webhook(request: Request, db: DbSession):
    """
    Delivery status webhook endpoint.

    Receives status updates from messaging providers (WhatsApp, SMS, etc.)
    Public endpoint -- no login required.
    """
    body = await request.json()

    external_id = body.get("external_id", "")
    status = body.get("status", "")
    error_message = body.get("error", "")

    if not external_id or not status:
        return JSONResponse({"error": "external_id and status required"}, status_code=400)

    # Search across all hubs for this external_id
    from sqlalchemy import select
    result = await db.execute(
        select(Message).where(Message.external_id == external_id, Message.is_deleted == False)  # noqa: E712
    )
    msg = result.scalar_one_or_none()

    if msg is None:
        return JSONResponse({"error": "Message not found"}, status_code=404)

    if status == "delivered":
        msg.mark_delivered()
    elif status == "read":
        msg.mark_read()
    elif status == "failed":
        msg.mark_failed(error=error_message)
    elif status == "sent":
        msg.mark_sent()

    await db.flush()

    return JSONResponse({"success": True, "message_id": str(msg.id)})
