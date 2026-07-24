import logging

from django.conf import settings
from django.utils.module_loading import import_string

from .events import NotificationEvent

logger = logging.getLogger("service_operations.notifications")

DEFAULT_BACKEND = "service_operations.notifications.backends.LoggingNotificationBackend"

_backend_instance = None


def _get_backend():
    global _backend_instance
    if _backend_instance is None:
        backend_path = getattr(settings, "NOTIFICATION_BACKEND", DEFAULT_BACKEND)
        backend_class = import_string(backend_path)
        _backend_instance = backend_class()
    return _backend_instance


def notify(event: NotificationEvent, recipient: str, **context) -> bool:
    """
    Fire a notification for `event` to `recipient`. Never raises - a
    misbehaving or unconfigured notification backend must not break the
    payment/activation flow that's calling this. Returns whether the
    configured backend accepted the notification.
    """
    if not recipient:
        logger.warning("notify(%s) skipped: no recipient given", getattr(event, "value", event))
        return False

    try:
        backend = _get_backend()
        return bool(backend.send(event, recipient, context))
    except Exception:
        logger.exception("Notification backend failed for event %s", getattr(event, "value", event))
        return False
