"""
AI tools for the Messaging module.

Uses @register_tool + AssistantTool class pattern.
All tools are async and use HubQuery for DB access.
"""

from __future__ import annotations

import uuid
from typing import Any


from app.ai.registry import AssistantTool, register_tool
from app.core.db.query import HubQuery
from app.core.db.transactions import atomic

from .models import Message, MessageAutomation, MessageTemplate


def _q(model, session, hub_id):
    return HubQuery(model, session, hub_id)


@register_tool
class ListMessageTemplates(AssistantTool):
    name = "list_message_templates"
    description = (
        "List message templates (WhatsApp, SMS, email). "
        "Read-only -- no side effects. "
        "Returns name, channel, category, subject, and active status."
    )
    module_id = "messaging"
    required_permission = "messaging.view_template"
    parameters = {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": "Filter by channel: whatsapp, sms, email, all.",
            },
            "is_active": {
                "type": "boolean",
                "description": "Filter by active status.",
            },
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        query = _q(MessageTemplate, db, hub_id)
        if args.get("channel"):
            query = query.filter(MessageTemplate.channel == args["channel"])
        if "is_active" in args:
            query = query.filter(MessageTemplate.is_active == args["is_active"])
        templates = await query.order_by(MessageTemplate.name).all()
        return {
            "templates": [{
                "id": str(t.id), "name": t.name, "channel": t.channel,
                "category": t.category, "subject": t.subject,
                "is_active": t.is_active,
            } for t in templates],
        }


@register_tool
class CreateMessageTemplate(AssistantTool):
    name = "create_message_template"
    description = (
        "Create a message template for WhatsApp/SMS/email. "
        "SIDE EFFECT: creates a new template record. Requires confirmation."
    )
    module_id = "messaging"
    required_permission = "messaging.add_template"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Template name."},
            "channel": {"type": "string", "description": "whatsapp, sms, email, all."},
            "category": {"type": "string", "description": "Template category."},
            "subject": {"type": "string", "description": "Email subject line."},
            "body": {"type": "string", "description": "Template body (supports {{variables}})."},
        },
        "required": ["name", "channel", "body"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        async with atomic(db) as session:
            t = MessageTemplate(
                hub_id=hub_id,
                name=args["name"],
                channel=args["channel"],
                category=args.get("category", "custom"),
                subject=args.get("subject", ""),
                body=args["body"],
            )
            session.add(t)
            await session.flush()
        return {"id": str(t.id), "name": t.name, "created": True}


@register_tool
class ListMessages(AssistantTool):
    name = "list_messages"
    description = (
        "List sent messages. "
        "Read-only -- no side effects. "
        "Returns channel, recipient, subject, status, and sent time."
    )
    module_id = "messaging"
    required_permission = "messaging.view_message"
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Filter by channel."},
            "status": {"type": "string", "description": "queued, sent, delivered, failed, read."},
            "limit": {"type": "integer", "description": "Maximum records to return (default 20)."},
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        query = _q(Message, db, hub_id)
        if args.get("channel"):
            query = query.filter(Message.channel == args["channel"])
        if args.get("status"):
            query = query.filter(Message.status == args["status"])
        limit = args.get("limit", 20)
        messages = await query.order_by(Message.created_at.desc()).limit(limit).all()
        return {
            "messages": [{
                "id": str(m.id), "channel": m.channel,
                "recipient_name": m.recipient_name, "subject": m.subject,
                "status": m.status,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            } for m in messages],
        }


@register_tool
class ListMessageAutomations(AssistantTool):
    name = "list_message_automations"
    description = (
        "List message automations (triggers like welcome, birthday, post_sale). "
        "Read-only -- no side effects."
    )
    module_id = "messaging"
    required_permission = "messaging.view_automation"
    parameters = {
        "type": "object",
        "properties": {
            "is_active": {"type": "boolean", "description": "Filter by active status."},
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        query = _q(MessageAutomation, db, hub_id)
        if "is_active" in args:
            query = query.filter(MessageAutomation.is_active == args["is_active"])
        automations = await query.order_by(MessageAutomation.name).all()
        return {
            "automations": [{
                "id": str(a.id), "name": a.name, "trigger": a.trigger,
                "channel": a.channel,
                "template": a.template.name if a.template else None,
                "is_active": a.is_active, "delay_hours": a.delay_hours,
            } for a in automations],
        }


@register_tool
class CreateMessageAutomation(AssistantTool):
    name = "create_message_automation"
    description = (
        "Create a message automation (e.g., welcome SMS, birthday email, post-sale thank you). "
        "SIDE EFFECT: creates a new automation record. Requires confirmation."
    )
    module_id = "messaging"
    required_permission = "messaging.add_automation"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Automation name."},
            "trigger": {"type": "string", "description": "welcome, birthday, post_sale, inactivity, etc."},
            "channel": {"type": "string", "description": "whatsapp, sms, email."},
            "template_id": {"type": "string", "description": "UUID of the template to use."},
            "delay_hours": {"type": "integer", "description": "Hours to wait before sending."},
        },
        "required": ["name", "trigger", "channel", "template_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        async with atomic(db) as session:
            a = MessageAutomation(
                hub_id=hub_id,
                name=args["name"],
                trigger=args["trigger"],
                channel=args["channel"],
                template_id=uuid.UUID(args["template_id"]),
                delay_hours=args.get("delay_hours", 0),
            )
            session.add(a)
            await session.flush()
        return {"id": str(a.id), "name": a.name, "created": True}
