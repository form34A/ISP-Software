import logging

from .base import NotificationBackend
from .events import NotificationEvent

logger = logging.getLogger("service_operations.notifications")


class LoggingNotificationBackend(NotificationBackend):
    """
    Default backend: logs the notification instead of sending it anywhere.
    Wiring a real gateway (SMS, email, push) later means writing a new
    NotificationBackend subclass and pointing settings.NOTIFICATION_BACKEND
    at it - nothing that calls `notify()` needs to change.
    """

    def send(self, event: NotificationEvent, recipient: str, context: dict) -> bool:
        logger.info("NOTIFY [%s] to %s | %s", event.value, recipient, context)
        return True
