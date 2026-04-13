"""
Messaging module services — ModuleService pattern.

Services: TemplateService, MessageService, AutomationService.
"""

from __future__ import annotations

import re
import uuid

from app.core.db.transactions import atomic
from app.modules.services import ModuleService, action

from messaging.models import Message, MessageAutomation, MessageTemplate


_KNOWN_TEMPLATE_VARIABLES = {
    "customer_name", "business_name", "appointment_date", "appointment_time",
    "service_name", "staff_name", "total_amount", "booking_reference",
    "order_reference", "reservation_date", "reservation_time", "party_size",
    "customer_phone", "customer_email", "hub_name", "hub_phone", "hub_address",
}

_TEMPLATE_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def _check_template_variables(body: str) -> list[str]:
    """Return list of undefined template variables found in body."""
    used = set(_TEMPLATE_VAR_RE.findall(body))
    return sorted(used - _KNOWN_TEMPLATE_VARIABLES)


# ============================================================================
# Template Service
# ============================================================================


class TemplateService(ModuleService):
    """Message template management (WhatsApp, SMS, email)."""

    @action(permission="view_template")
    async def list_templates(
        self,
        *,
        channel: str = "",
        is_active: bool | None = None,
    ):
        """List message templates with optional channel and active filters."""
        query = self.q(MessageTemplate)
        if channel:
            query = query.filter(MessageTemplate.channel == channel)
        if is_active is not None:
            query = query.filter(MessageTemplate.is_active == is_active)
        templates = await query.order_by(MessageTemplate.name).all()
        return {
            "templates": [{
                "id": str(t.id),
                "name": t.name,
                "channel": t.channel,
                "category": t.category,
                "subject": t.subject,
                "is_active": t.is_active,
            } for t in templates],
        }

    @action(permission="add_template", mutates=True)
    async def create_template(
        self,
        *,
        name: str,
        channel: str,
        body: str,
        category: str = "custom",
        subject: str = "",
    ):
        """Create a message template for WhatsApp/SMS/email."""
        undefined_vars = _check_template_variables(body)
        if subject:
            undefined_vars.extend(_check_template_variables(subject))
            undefined_vars = sorted(set(undefined_vars))

        async with atomic(self.db) as session:
            t = MessageTemplate(
                hub_id=self.hub_id,
                name=name,
                channel=channel,
                category=category,
                subject=subject,
                body=body,
            )
            session.add(t)
            await session.flush()

        result: dict = {"id": str(t.id), "name": t.name, "created": True}
        if undefined_vars:
            result["warning"] = (
                f"Template uses undefined variables: "
                f"{', '.join('{{' + v + '}}' for v in undefined_vars)}. "
                f"Known variables: "
                f"{', '.join('{{' + v + '}}' for v in sorted(_KNOWN_TEMPLATE_VARIABLES))}."
            )
        return result

    @action(permission="add_template", mutates=True)
    async def bulk_create_templates(self, *, templates: list[dict]):
        """Create multiple message templates at once."""
        created = 0
        errors = []
        warnings = []

        for item in templates:
            try:
                undefined_vars = _check_template_variables(item["body"])
                if item.get("subject"):
                    undefined_vars.extend(_check_template_variables(item["subject"]))
                    undefined_vars = sorted(set(undefined_vars))

                async with atomic(self.db) as session:
                    t = MessageTemplate(
                        hub_id=self.hub_id,
                        name=item["name"],
                        channel=item["channel"],
                        category=item.get("category", "custom"),
                        subject=item.get("subject", ""),
                        body=item["body"],
                    )
                    session.add(t)
                    await session.flush()

                created += 1
                if undefined_vars:
                    warnings.append({
                        "name": item["name"],
                        "warning": (
                            f"Uses undefined variables: "
                            f"{', '.join('{{' + v + '}}' for v in undefined_vars)}."
                        ),
                    })
            except Exception as e:
                errors.append({"name": item.get("name"), "error": str(e)})

        return {"success": True, "created": created, "warnings": warnings, "errors": errors}


# ============================================================================
# Message Service
# ============================================================================


class MessageService(ModuleService):
    """Sent message log."""

    @action(permission="view_message")
    async def list_messages(
        self,
        *,
        channel: str = "",
        status: str = "",
        limit: int = 20,
    ):
        """List sent messages with optional channel and status filters."""
        query = self.q(Message)
        if channel:
            query = query.filter(Message.channel == channel)
        if status:
            query = query.filter(Message.status == status)
        messages = await query.order_by(Message.created_at.desc()).limit(limit).all()
        return {
            "messages": [{
                "id": str(m.id),
                "channel": m.channel,
                "recipient_name": m.recipient_name,
                "subject": m.subject,
                "status": m.status,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            } for m in messages],
        }


# ============================================================================
# Automation Service
# ============================================================================


class AutomationService(ModuleService):
    """Message automation management (CRM triggers)."""

    @action(permission="view_automation")
    async def list_automations(self, *, is_active: bool | None = None):
        """List message automations (welcome, birthday, post_sale, etc.)."""
        query = self.q(MessageAutomation)
        if is_active is not None:
            query = query.filter(MessageAutomation.is_active == is_active)
        automations = await query.order_by(MessageAutomation.name).all()
        return {
            "automations": [{
                "id": str(a.id),
                "name": a.name,
                "trigger": a.trigger,
                "channel": a.channel,
                "template": a.template.name if a.template else None,
                "is_active": a.is_active,
                "delay_hours": a.delay_hours,
            } for a in automations],
        }

    @action(permission="add_automation", mutates=True)
    async def create_automation(
        self,
        *,
        name: str,
        trigger: str,
        channel: str,
        template_id: str,
        delay_hours: int = 0,
    ):
        """Create a message automation (e.g., welcome SMS, birthday email)."""
        async with atomic(self.db) as session:
            a = MessageAutomation(
                hub_id=self.hub_id,
                name=name,
                trigger=trigger,
                channel=channel,
                template_id=uuid.UUID(template_id),
                delay_hours=delay_hours,
            )
            session.add(a)
            await session.flush()
        return {"id": str(a.id), "name": a.name, "created": True}
