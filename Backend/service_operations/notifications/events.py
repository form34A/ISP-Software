from enum import Enum


class NotificationEvent(str, Enum):
    """Named events the rest of the app can raise notifications for.

    Adding a new event here is the only place the "what can we notify about"
    vocabulary is defined - backends decide how (or whether) to act on each
    one.
    """

    PURCHASE_CONFIRMED = "purchase_confirmed"
    PLAN_ACTIVATED = "plan_activated"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
