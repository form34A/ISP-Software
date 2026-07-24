from abc import ABC, abstractmethod

from .events import NotificationEvent


class NotificationBackend(ABC):
    """
    Interface every notification backend must implement. `send` should never
    raise for expected delivery failures (network errors, unconfigured
    gateway, etc.) - return False and let the caller/dispatcher log it,
    so a broken notification channel can never take down the payment or
    activation flow that triggered it.
    """

    @abstractmethod
    def send(self, event: NotificationEvent, recipient: str, context: dict) -> bool:
        """
        recipient: phone number (or other channel address) to notify.
        context: event-specific data (e.g. plan name, amount, expiry date).
        Returns True if the notification was accepted for delivery.
        """
        raise NotImplementedError
