"""
JWT-over-WebSocket authentication middleware for Django Channels.

Browsers can't set an Authorization header on a WebSocket handshake, so
authenticated consumers need the JWT passed as a `?token=...` query param
instead. This extracts the token-parsing/validation logic that already
existed per-consumer in sms_automation/consumers.py (SMSStatusConsumer /
SMSBroadcastConsumer's authenticate_user()) into a reusable middleware so
any websocket route can use it, rather than reimplementing it per consumer.
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


@database_sync_to_async
def _get_user_from_token(token):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        access_token = AccessToken(token)
        return User.objects.get(id=access_token["user_id"])
    except Exception as e:
        logger.debug(f"Token authentication failed: {e}")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Populates scope["user"] from a `?token=<JWT>` query string param.

    Wrap this around AuthMiddlewareStack (JWTAuthMiddleware(AuthMiddlewareStack(...)))
    so existing session-cookie auth still works as a fallback when no token
    is present in the query string.
    """

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]

        if token:
            # Token present: resolve it and skip session lookup entirely
            # (AuthMiddlewareStack's populate_scope only runs if "user"
            # isn't already in scope, so this takes priority).
            scope["user"] = await _get_user_from_token(token)
        else:
            # No token: leave scope["user"] unset so the wrapped
            # AuthMiddlewareStack can still fall back to session-cookie auth.
            logger.debug("No token provided in WebSocket connection")

        return await super().__call__(scope, receive, send)
