"""
Messaging module event subscriptions.

Registers handlers on the AsyncEventBus during module load.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.events.bus import AsyncEventBus

logger = logging.getLogger(__name__)

MODULE_ID = "messaging"


def register_events(bus: AsyncEventBus, module_id: str) -> None:
    """
    Register event handlers for the messaging module.

    Called by ModuleRuntime during module load.
    """
    bus.subscribe(
        "customers.created",
        _on_customer_created,
        module_id=module_id,
    )
    bus.subscribe(
        "sales.completed",
        _on_sale_completed,
        module_id=module_id,
    )
    bus.subscribe(
        "leave.request_approved",
        _on_leave_request_approved,
        module_id=module_id,
    )


async def _on_customer_created(
    event: str,
    sender: object = None,
    customer: object = None,
    **kwargs,
) -> None:
    """
    When a new customer is created, check for welcome automations.
    """
    if customer is None:
        return
    logger.info(
        "Messaging: new customer %s — checking welcome automations",
        getattr(customer, "id", "?"),
    )


async def _on_sale_completed(
    event: str,
    sender: object = None,
    sale: object = None,
    **kwargs,
) -> None:
    """
    When a sale completes, check for post-sale messaging automations.
    """
    if sale is None:
        return
    logger.info(
        "Messaging: sale %s completed — checking post-sale automations",
        getattr(sale, "id", "?"),
    )


async def _on_leave_request_approved(
    event: str,
    sender: object = None,
    leave_request: object = None,
    **kwargs: object,
) -> None:
    """
    When a leave request is approved, notify the employee via the configured
    messaging channel (placeholder — future push/email integration).
    """
    if leave_request is None:
        return
    logger.info(
        "Messaging: leave request approved for %s — notification pending channel setup",
        getattr(leave_request, "employee_name", "?"),
    )
