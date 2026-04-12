"""
Thread-safe registry for ChannelDriver instances.

Drivers register themselves on module activation and unregister on deactivation.
The MessageDispatcher uses this registry to route outbound messages.
"""

from __future__ import annotations

from threading import RLock

from .base import ChannelDriver

_drivers: dict[str, ChannelDriver] = {}
_lock = RLock()


def register_driver(driver: ChannelDriver) -> None:
    """Register a channel driver. Replaces any existing driver with the same channel_id."""
    with _lock:
        _drivers[driver.channel_id] = driver


def unregister_driver(channel_id: str) -> None:
    """Unregister a driver by channel_id. No-op if not registered."""
    with _lock:
        _drivers.pop(channel_id, None)


def get_driver(channel_id: str) -> ChannelDriver | None:
    """Return the driver for channel_id, or None if not registered."""
    with _lock:
        return _drivers.get(channel_id)


def list_drivers() -> list[ChannelDriver]:
    """Return all registered drivers as a list."""
    with _lock:
        return list(_drivers.values())
