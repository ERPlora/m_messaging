"""
Messaging module HTMX views -- FastAPI router.

Replaces Django views.py + urls.py. Uses @htmx_view decorator
(partial for HTMX requests, full page for direct navigation).
Mounted at /m/messaging/ by ModuleRuntime.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, UTC

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_

from app.core.db.query import HubQuery
from app.core.db.transactions import atomic
from app.core.dependencies import CurrentUser, DbSession, HubId
from app.core.htmx import add_message, htmx_redirect, htmx_view

from .models import (
    AUTOMATION_TRIGGER_CHOICES,
    AUTOMATION_TRIGGER_LABELS,
    Campaign,
    Message,
    MessageAutomation,
    MessageTemplate,
    MessagingSettings,
)
from .webhooks.router import router as _webhook_router

logger = logging.getLogger(__name__)

router = APIRouter()

# Include webhook router (no auth — Meta webhooks are public)
router.include_router(_webhook_router)

PER_PAGE = 25


def _q(model, db, hub_id):
    return HubQuery(model, db, hub_id)


# ============================================================================
# Helper: get trigger choices as list of (value, label) tuples
# ============================================================================

def _trigger_choices() -> list[tuple[str, str]]:
    return [(t, AUTOMATION_TRIGGER_LABELS.get(t, t)) for t in AUTOMATION_TRIGGER_CHOICES]


# ============================================================================
# Dashboard
# ============================================================================

@router.get("/")
@htmx_view(module_id="messaging", view_id="dashboard")
async def dashboard(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """Messaging overview: sent today, delivery rate, recent messages."""
    today = datetime.now(UTC).date()

    total_messages = await _q(Message, db, hub_id).count()
    sent_today = await _q(Message, db, hub_id).filter(
        func.date(Message.created_at) == today,
    ).count()
    delivered_count = await _q(Message, db, hub_id).filter(
        Message.status.in_(["delivered", "read"]),
    ).count()
    failed_count = await _q(Message, db, hub_id).filter(
        Message.status == "failed",
    ).count()
    delivery_rate = round((delivered_count / total_messages * 100), 1) if total_messages > 0 else 0

    recent_messages = await _q(Message, db, hub_id).order_by(
        Message.created_at.desc(),
    ).limit(10).all()

    active_campaigns = await _q(Campaign, db, hub_id).filter(
        Campaign.status.in_(["sending", "scheduled"]),
    ).count()

    template_count = await _q(MessageTemplate, db, hub_id).filter(
        MessageTemplate.is_active == True,  # noqa: E712
    ).count()

    return {
        "total_messages": total_messages,
        "sent_today": sent_today,
        "delivered_count": delivered_count,
        "failed_count": failed_count,
        "delivery_rate": delivery_rate,
        "recent_messages": recent_messages,
        "active_campaigns": active_campaigns,
        "template_count": template_count,
    }


# ============================================================================
# Messages
# ============================================================================

@router.get("/messages")
@htmx_view(module_id="messaging", view_id="messages")
async def messages_list(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    q: str = "", channel: str = "", status: str = "", page: int = 1,
):
    """Message log with filters (channel, status, search)."""
    query = _q(Message, db, hub_id)

    if channel:
        query = query.filter(Message.channel == channel)
    if status:
        query = query.filter(Message.status == status)
    if q:
        query = query.filter(or_(
            Message.recipient_name.ilike(f"%{q}%"),
            Message.recipient_contact.ilike(f"%{q}%"),
            Message.subject.ilike(f"%{q}%"),
            Message.body.ilike(f"%{q}%"),
        ))

    total = await query.count()
    messages = await query.order_by(Message.created_at.desc()).offset(
        (page - 1) * PER_PAGE
    ).limit(PER_PAGE).all()

    total_pages = (total + PER_PAGE - 1) // PER_PAGE if total > 0 else 1

    return {
        "messages_list": messages,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "search_query": q,
        "channel_filter": channel,
        "status_filter": status,
    }


@router.get("/messages/{pk}")
@htmx_view(module_id="messaging", view_id="messages")
async def message_detail(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """View a single message."""
    message = await _q(Message, db, hub_id).get(pk)
    if message is None:
        return JSONResponse({"error": "Message not found"}, status_code=404)
    return {"message": message}


@router.get("/messages/compose")
@htmx_view(module_id="messaging", view_id="messages")
async def compose_message(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    customer: str = "", channel: str = "",
):
    """Compose and send a single message."""
    initial = {}
    if channel:
        initial["channel"] = channel
    if customer:
        try:
            from customers.models import Customer
            c = await _q(Customer, db, hub_id).get(uuid.UUID(customer))
            if c:
                initial["customer_id"] = str(c.id)
                initial["recipient_name"] = c.name
                if channel == "email":
                    initial["recipient_contact"] = c.email
                else:
                    initial["recipient_contact"] = c.phone
        except Exception:
            pass

    templates = await _q(MessageTemplate, db, hub_id).filter(
        MessageTemplate.is_active == True,  # noqa: E712
    ).order_by(MessageTemplate.name).all()

    return {
        "initial": initial,
        "templates": templates,
    }


@router.post("/messages/compose")
async def compose_message_post(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Send a composed message."""
    form = await request.form()
    channel = form.get("channel", "")
    recipient_contact = form.get("recipient_contact", "")
    body = form.get("body", "")

    if not channel or not recipient_contact or not body:
        add_message(request, "error", "Channel, contact, and body are required")
        return htmx_redirect("/m/messaging/messages/compose")

    template_id = form.get("template") or None
    customer_id = form.get("customer") or None

    async with atomic(db) as session:
        msg = Message(
            hub_id=hub_id,
            channel=channel,
            recipient_name=form.get("recipient_name", ""),
            recipient_contact=recipient_contact,
            subject=form.get("subject", ""),
            body=body,
            status="queued",
            template_id=uuid.UUID(template_id) if template_id else None,
            customer_id=uuid.UUID(customer_id) if customer_id else None,
        )
        session.add(msg)
        await session.flush()
        msg.mark_sent()

    add_message(request, "success", "Message sent successfully")
    return htmx_redirect("/m/messaging/messages")


# ============================================================================
# Templates
# ============================================================================

@router.get("/templates")
@htmx_view(module_id="messaging", view_id="templates")
async def templates_list(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    q: str = "",
):
    """Template list."""
    query = _q(MessageTemplate, db, hub_id)
    if q:
        query = query.filter(or_(
            MessageTemplate.name.ilike(f"%{q}%"),
            MessageTemplate.body.ilike(f"%{q}%"),
        ))
    templates = await query.order_by(MessageTemplate.category, MessageTemplate.name).all()
    return {"templates": templates, "search_query": q}


@router.get("/templates/create")
@htmx_view(module_id="messaging", view_id="templates")
async def template_create(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Create a new template -- form."""
    return {"is_edit": False}


@router.post("/templates/create")
async def template_create_post(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Create a new template."""
    form = await request.form()
    async with atomic(db) as session:
        template = MessageTemplate(
            hub_id=hub_id,
            name=form.get("name", ""),
            channel=form.get("channel", "all"),
            category=form.get("category", "custom"),
            subject=form.get("subject", ""),
            body=form.get("body", ""),
            is_active=form.get("is_active") in ("on", "true", True),
        )
        session.add(template)
    add_message(request, "success", "Template created successfully")
    return htmx_redirect("/m/messaging/templates")


@router.get("/templates/{pk}/edit")
@htmx_view(module_id="messaging", view_id="templates")
async def template_edit(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Edit an existing template -- form."""
    template = await _q(MessageTemplate, db, hub_id).get(pk)
    if template is None:
        return JSONResponse({"error": "Template not found"}, status_code=404)
    return {"msg_template": template, "is_edit": True}


@router.post("/templates/{pk}/edit")
async def template_edit_post(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Update an existing template."""
    template = await _q(MessageTemplate, db, hub_id).get(pk)
    if template is None:
        return JSONResponse({"error": "Template not found"}, status_code=404)

    form = await request.form()
    for field in ("name", "channel", "category", "subject", "body"):
        value = form.get(field)
        if value is not None:
            setattr(template, field, value)
    is_active = form.get("is_active")
    template.is_active = is_active in ("on", "true", True)
    await db.flush()

    add_message(request, "success", "Template updated successfully")
    return htmx_redirect("/m/messaging/templates")


@router.post("/templates/{pk}/delete")
async def template_delete(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Soft-delete a template."""
    template = await _q(MessageTemplate, db, hub_id).get(pk)
    if template is None:
        return JSONResponse({"error": "Template not found"}, status_code=404)

    if template.is_system:
        add_message(request, "error", "System templates cannot be deleted")
        return htmx_redirect("/m/messaging/templates")

    await _q(MessageTemplate, db, hub_id).delete(pk)
    add_message(request, "success", "Template deleted successfully")
    return htmx_redirect("/m/messaging/templates")


# ============================================================================
# Campaigns
# ============================================================================

@router.get("/campaigns")
@htmx_view(module_id="messaging", view_id="campaigns")
async def campaigns_list(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    q: str = "", status: str = "",
):
    """Campaign list."""
    query = _q(Campaign, db, hub_id)
    if status:
        query = query.filter(Campaign.status == status)
    if q:
        query = query.filter(or_(
            Campaign.name.ilike(f"%{q}%"),
            Campaign.description.ilike(f"%{q}%"),
        ))
    campaigns = await query.order_by(Campaign.created_at.desc()).all()
    return {"campaigns": campaigns, "search_query": q, "status_filter": status}


@router.get("/campaigns/create")
@htmx_view(module_id="messaging", view_id="campaigns")
async def campaign_create(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Create a new campaign -- form."""
    templates = await _q(MessageTemplate, db, hub_id).filter(
        MessageTemplate.is_active == True,  # noqa: E712
    ).order_by(MessageTemplate.name).all()
    return {"templates": templates, "is_edit": False}


@router.post("/campaigns/create")
async def campaign_create_post(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Create a new campaign."""
    form = await request.form()
    template_id = form.get("template") or None
    scheduled_at_str = form.get("scheduled_at", "").strip()
    scheduled_at = None
    if scheduled_at_str:
        try:
            scheduled_at = datetime.fromisoformat(scheduled_at_str)
        except ValueError:
            pass

    async with atomic(db) as session:
        campaign = Campaign(
            hub_id=hub_id,
            name=form.get("name", ""),
            description=form.get("description", ""),
            channel=form.get("channel", "email"),
            template_id=uuid.UUID(template_id) if template_id else None,
            scheduled_at=scheduled_at,
        )
        session.add(campaign)
    add_message(request, "success", "Campaign created successfully")
    return htmx_redirect("/m/messaging/campaigns")


@router.get("/campaigns/{pk}")
@htmx_view(module_id="messaging", view_id="campaigns")
async def campaign_detail(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """View campaign details and stats."""
    campaign = await _q(Campaign, db, hub_id).get(pk)
    if campaign is None:
        return JSONResponse({"error": "Campaign not found"}, status_code=404)
    return {"campaign": campaign}


@router.post("/campaigns/{pk}/start")
async def campaign_start(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Start sending a campaign."""
    campaign = await _q(Campaign, db, hub_id).get(pk)
    if campaign is None:
        return JSONResponse({"error": "Campaign not found"}, status_code=404)

    if campaign.status not in ("draft", "scheduled"):
        add_message(request, "error", "Campaign cannot be started in its current state")
    else:
        campaign.start()
        await db.flush()
        add_message(request, "success", "Campaign started")

    return htmx_redirect(f"/m/messaging/campaigns/{pk}")


@router.post("/campaigns/{pk}/cancel")
async def campaign_cancel(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Cancel a campaign."""
    campaign = await _q(Campaign, db, hub_id).get(pk)
    if campaign is None:
        return JSONResponse({"error": "Campaign not found"}, status_code=404)

    if campaign.status in ("completed", "cancelled"):
        add_message(request, "error", "Campaign is already finished")
    else:
        campaign.cancel()
        await db.flush()
        add_message(request, "success", "Campaign cancelled")

    return htmx_redirect(f"/m/messaging/campaigns/{pk}")


# ============================================================================
# Automations
# ============================================================================

@router.get("/automations")
@htmx_view(module_id="messaging", view_id="automations")
async def automations_list(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    q: str = "",
):
    """List all automations."""
    query = _q(MessageAutomation, db, hub_id)
    if q:
        query = query.filter(or_(
            MessageAutomation.name.ilike(f"%{q}%"),
            MessageAutomation.description.ilike(f"%{q}%"),
        ))
    automations = await query.order_by(MessageAutomation.name).all()
    return {
        "automations": automations,
        "search_query": q,
        "trigger_choices": _trigger_choices(),
    }


@router.get("/automations/add")
@htmx_view(module_id="messaging", view_id="automations")
async def automation_add(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Add automation -- form."""
    templates = await _q(MessageTemplate, db, hub_id).filter(
        MessageTemplate.is_active == True,  # noqa: E712
    ).order_by(MessageTemplate.name).all()
    return {
        "templates": templates,
        "trigger_choices": _trigger_choices(),
    }


@router.post("/automations/add")
async def automation_add_post(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Create a new automation."""
    form = await request.form()
    name = form.get("name", "").strip()
    if not name:
        add_message(request, "error", "Name is required")
        return htmx_redirect("/m/messaging/automations/add")

    template_id = form.get("template") or None
    conditions: dict = {}
    inactivity_days = form.get("inactivity_days", "").strip()
    if inactivity_days:
        conditions["inactivity_days"] = int(inactivity_days)

    async with atomic(db) as session:
        automation = MessageAutomation(
            hub_id=hub_id,
            name=name,
            description=form.get("description", "").strip(),
            trigger=form.get("trigger", "custom"),
            channel=form.get("channel", "email"),
            template_id=uuid.UUID(template_id) if template_id else None,
            delay_hours=int(form.get("delay_hours", "0") or "0"),
            is_active=form.get("is_active") == "on",
            conditions=conditions,
        )
        session.add(automation)

    add_message(request, "success", "Automation created successfully")
    return htmx_redirect("/m/messaging/automations")


@router.get("/automations/{pk}/edit")
@htmx_view(module_id="messaging", view_id="automations")
async def automation_edit(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Edit automation -- form."""
    automation = await _q(MessageAutomation, db, hub_id).get(pk)
    if automation is None:
        return JSONResponse({"error": "Automation not found"}, status_code=404)
    templates = await _q(MessageTemplate, db, hub_id).filter(
        MessageTemplate.is_active == True,  # noqa: E712
    ).order_by(MessageTemplate.name).all()
    return {
        "automation": automation,
        "templates": templates,
        "trigger_choices": _trigger_choices(),
    }


@router.post("/automations/{pk}/edit")
async def automation_edit_post(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Update an automation."""
    automation = await _q(MessageAutomation, db, hub_id).get(pk)
    if automation is None:
        return JSONResponse({"error": "Automation not found"}, status_code=404)

    form = await request.form()
    name = form.get("name", "").strip()
    if not name:
        add_message(request, "error", "Name is required")
        return htmx_redirect(f"/m/messaging/automations/{pk}/edit")

    template_id = form.get("template") or None
    conditions: dict = {}
    inactivity_days = form.get("inactivity_days", "").strip()
    if inactivity_days:
        conditions["inactivity_days"] = int(inactivity_days)

    automation.name = name
    automation.description = form.get("description", "").strip()
    automation.trigger = form.get("trigger", automation.trigger)
    automation.channel = form.get("channel", automation.channel)
    automation.template_id = uuid.UUID(template_id) if template_id else None
    automation.delay_hours = int(form.get("delay_hours", "0") or "0")
    automation.is_active = form.get("is_active") == "on"
    automation.conditions = conditions
    await db.flush()

    add_message(request, "success", "Automation updated successfully")
    return htmx_redirect("/m/messaging/automations")


@router.post("/automations/{pk}/delete")
async def automation_delete(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Soft-delete automation."""
    await _q(MessageAutomation, db, hub_id).delete(pk)
    add_message(request, "success", "Automation deleted")
    return htmx_redirect("/m/messaging/automations")


@router.post("/automations/{pk}/toggle")
async def automation_toggle(
    request: Request, pk: uuid.UUID, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Toggle automation active/inactive."""
    automation = await _q(MessageAutomation, db, hub_id).get(pk)
    if automation is None:
        return JSONResponse({"error": "Automation not found"}, status_code=404)

    automation.is_active = not automation.is_active
    await db.flush()

    status_text = "activated" if automation.is_active else "deactivated"
    add_message(request, "success", f"Automation {status_text}")
    return htmx_redirect("/m/messaging/automations")


# ============================================================================
# Settings
# ============================================================================

@router.get("/settings")
@htmx_view(module_id="messaging", view_id="settings")
async def settings_view(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """View messaging settings."""
    settings = await _q(MessagingSettings, db, hub_id).first()
    if settings is None:
        async with atomic(db) as session:
            settings = MessagingSettings(hub_id=hub_id)
            session.add(settings)
            await session.flush()

    total_messages = await _q(Message, db, hub_id).count()
    total_templates = await _q(MessageTemplate, db, hub_id).count()
    total_campaigns = await _q(Campaign, db, hub_id).count()

    return {
        "settings": settings,
        "total_messages": total_messages,
        "total_templates": total_templates,
        "total_campaigns": total_campaigns,
    }


@router.post("/settings/save")
async def settings_save(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Save messaging settings."""
    settings = await _q(MessagingSettings, db, hub_id).first()
    if settings is None:
        settings = MessagingSettings(hub_id=hub_id)
        db.add(settings)
        await db.flush()

    form = await request.form()

    # Boolean fields
    for field in (
        "whatsapp_enabled", "sms_enabled", "email_enabled",
        "email_smtp_use_tls", "appointment_reminder_enabled",
        "booking_confirmation_enabled",
    ):
        setattr(settings, field, form.get(field) in ("on", "true", True))

    # String fields
    for field in (
        "whatsapp_api_token", "whatsapp_phone_id", "whatsapp_business_id",
        "sms_provider", "sms_api_key", "sms_sender_name",
        "email_from_name", "email_from_address",
        "email_smtp_host", "email_smtp_username", "email_smtp_password",
    ):
        value = form.get(field)
        if value is not None:
            setattr(settings, field, value)

    # Integer fields
    for field in ("email_smtp_port", "appointment_reminder_hours"):
        value = form.get(field)
        if value is not None and value != "":
            setattr(settings, field, int(value))

    await db.flush()
    add_message(request, "success", "Settings saved successfully")
    return htmx_redirect("/m/messaging/settings")


# ============================================================================
# Unified Inbox (multi-channel: WhatsApp + Email + future channels)
# ============================================================================

@router.get("/inbox")
@htmx_view(module_id="messaging", view_id="inbox", partial_template="messaging/partials/inbox_content.html")
async def inbox(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    hub_id: HubId,
    channel: str = "",
    status: str = "",
    q: str = "",
):
    """Unified inbox — lists all conversations across all channels.

    Pulls from communications.Thread (email + future channels) and
    whatsapp_inbox.WhatsAppConversation (for legacy WhatsApp data).

    Filters: channel, status, search query.
    """
    conversations: list[dict] = []

    # --- WhatsApp conversations (from whatsapp_inbox module) ---
    if not channel or channel == "whatsapp":
        try:
            from whatsapp_inbox.models import WhatsAppConversation  # type: ignore[import]
            wa_query = _q(WhatsAppConversation, db, hub_id)
            if status:
                wa_query = wa_query.filter(WhatsAppConversation.status == status)
            if q:
                wa_query = wa_query.filter(WhatsAppConversation.contact_name.ilike(f"%{q}%"))
            wa_convs = await wa_query.order_by(WhatsAppConversation.last_message_at.desc()).all()

            for conv in wa_convs:
                conversations.append({
                    "id": str(conv.id),
                    "channel": "whatsapp",
                    "channel_icon": "logo-whatsapp",
                    "contact_name": conv.contact_name,
                    "contact_identifier": conv.wa_contact_id,
                    "last_message_at": conv.last_message_at,
                    "status": conv.status,
                    "unread_count": conv.unread_count,
                    "subject": "",
                    "detail_url": f"/m/whatsapp_inbox/conversation/{conv.id}",
                })
        except ImportError:
            pass
        except Exception:
            logger.exception("[messaging inbox] Error fetching WhatsApp conversations")

    # --- Email / other threads (from communications module) ---
    if not channel or channel in ("email", "instagram", "facebook"):
        try:
            from communications.models import Thread  # type: ignore[import]
            from sqlalchemy import select

            stmt = select(Thread).where(
                Thread.hub_id == hub_id,
                Thread.is_deleted.is_(False),
            )
            if channel:
                stmt = stmt.where(Thread.channel == channel)
            if status:
                stmt = stmt.where(Thread.status == status)
            if q:
                stmt = stmt.where(or_(
                    Thread.contact_name.ilike(f"%{q}%"),
                    Thread.subject.ilike(f"%{q}%"),
                ))
            stmt = stmt.order_by(Thread.last_message_at.desc()).limit(100)

            result = await db.execute(stmt)
            threads = result.scalars().all()

            for thread in threads:
                icon_map = {
                    "email": "mail-outline",
                    "instagram": "logo-instagram",
                    "facebook": "logo-facebook",
                }
                conversations.append({
                    "id": str(thread.id),
                    "channel": thread.channel,
                    "channel_icon": icon_map.get(thread.channel, "chatbubble-outline"),
                    "contact_name": thread.contact_name or thread.contact_identifier,
                    "contact_identifier": thread.contact_identifier,
                    "last_message_at": thread.last_message_at,
                    "status": thread.status,
                    "unread_count": thread.unread_count,
                    "subject": thread.subject,
                    "detail_url": f"/m/communications/thread/{thread.id}",
                })
        except ImportError:
            pass
        except Exception:
            logger.exception("[messaging inbox] Error fetching communication threads")

    # Sort all conversations by last_message_at (newest first)
    conversations.sort(
        key=lambda c: c["last_message_at"] or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    # Available channels for filter dropdown
    available_channels = [
        {"id": "whatsapp", "label": "WhatsApp", "icon": "logo-whatsapp"},
        {"id": "email", "label": "Email", "icon": "mail-outline"},
    ]

    return {
        "conversations": conversations,
        "channel_filter": channel,
        "status_filter": status,
        "search_query": q,
        "available_channels": available_channels,
        "total": len(conversations),
    }
