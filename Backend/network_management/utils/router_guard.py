"""
Safety gate for router writes.

Every code path that creates, modifies, or removes a hotspot/PPPoE user entry
on a physical router must call `ensure_router_manages_hotspot_users(router, action)`
before issuing the RouterOS/Ubiquiti/etc. command. Routers default to
`manages_hotspot_users=False`, so nothing can write to a router until someone
explicitly flips that flag on for it.
"""

import logging

logger = logging.getLogger(__name__)


class RouterNotManagedError(Exception):
    """Raised when code attempts to write hotspot/PPPoE users to a router that
    SurfZone has not been explicitly enabled to manage."""


def ensure_router_manages_hotspot_users(router, action: str) -> None:
    """
    Refuse to proceed if `router.manages_hotspot_users` is not True.

    Logs a clear warning (with router id/name and the attempted action) and
    raises RouterNotManagedError so the caller returns an explicit error
    response instead of silently doing nothing or crashing with a generic
    exception further down.
    """
    if getattr(router, "manages_hotspot_users", False):
        return

    router_label = f"{getattr(router, 'name', '?')} (id={getattr(router, 'id', '?')})"
    logger.warning(
        "Refusing to %s on router %s: manages_hotspot_users is False for this router.",
        action, router_label,
    )
    raise RouterNotManagedError(
        f"Router {router_label} is not enabled for SurfZone-managed hotspot/PPPoE "
        f"users (manages_hotspot_users=False); refusing to {action}."
    )
