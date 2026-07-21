"""
Read-only live active-sessions endpoint - reads /ppp/active and
/ip/hotspot/active directly off the router (same RouterOsApiPool connection
pattern as RouterStatsView) and returns a unified session list. Makes no
writes and no disconnect calls; if the router is unreachable, responds 200
with an empty list and reachable: false instead of erroring.
"""

import logging
import re

from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError, RouterOsApiCommunicationError

from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from network_management.models.router_management_model import Router

logger = logging.getLogger(__name__)

# PPPoE comments look like "Name | 254724303504 | Exp: 2026-07-26 23:59:00";
# hotspot comments look like "Exp: 2026-08-01 18:29:11" (no name/phone).
# Both are parsed defensively - either piece missing/unrecognised just stays None.
_PHONE_RE = re.compile(r'^\+?\d{7,15}$')
_EXPIRY_RE = re.compile(r'exp\s*:\s*(.+)', re.IGNORECASE)


def parse_comment(comment):
    """Pull (phone, expiry) out of a router comment field. Never raises."""
    phone = None
    expiry = None
    if not comment:
        return phone, expiry
    try:
        for part in comment.split('|'):
            part = part.strip()
            expiry_match = _EXPIRY_RE.match(part)
            if expiry_match:
                expiry = expiry_match.group(1).strip()
                continue
            if _PHONE_RE.match(part):
                phone = part
    except Exception:
        logger.warning("Failed to parse session comment: %r", comment, exc_info=True)
        return None, None
    return phone, expiry


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_session(session_type, row):
    """Map one raw /ppp/active or /ip/hotspot/active row to the unified shape."""
    comment = row.get('comment') or ''
    phone, expiry = parse_comment(comment)

    if session_type == 'pppoe':
        username = row.get('name')
        mac_address = row.get('caller-id') or None
        bytes_in = None
        bytes_out = None
    else:
        username = row.get('user')
        mac_address = row.get('mac-address') or None
        bytes_in = _safe_int(row.get('bytes-in'))
        bytes_out = _safe_int(row.get('bytes-out'))

    return {
        'type': session_type,
        'username': username,
        'phone': phone,
        'expiry': expiry,
        'address': row.get('address'),
        'mac_address': mac_address,
        'uptime': row.get('uptime'),
        'bytes_in': bytes_in,
        'bytes_out': bytes_out,
        'comment': comment,
    }


class LiveSessionsView(APIView):
    """
    GET /routers/<pk>/live-sessions/

    Read-only. Connects live to the router and returns its current PPPoE +
    hotspot active sessions in a unified shape. 404 if the router row
    doesn't exist; 200 with reachable: false (not a 5xx) if the router
    itself can't be reached.
    """
    permission_classes = [IsAuthenticated]

    def get_router(self, pk):
        return get_object_or_404(Router, pk=pk, is_active=True)

    def get(self, request, pk):
        router = self.get_router(pk)
        sessions = []
        reachable = True

        try:
            api_pool = RouterOsApiPool(
                router.ip,
                username=router.username,
                password=router.password,
                port=router.port,
                plaintext_login=True
            )
            api = api_pool.get_api()

            pppoe_active = api.get_resource('/ppp/active').get() or []
            hotspot_active = api.get_resource('/ip/hotspot/active').get() or []

            api_pool.disconnect()

            for row in pppoe_active:
                try:
                    sessions.append(build_session('pppoe', row))
                except Exception:
                    logger.warning("Skipping malformed pppoe session row: %r", row, exc_info=True)
            for row in hotspot_active:
                try:
                    sessions.append(build_session('hotspot', row))
                except Exception:
                    logger.warning("Skipping malformed hotspot session row: %r", row, exc_info=True)

        except (RouterOsApiConnectionError, RouterOsApiCommunicationError):
            logger.warning("Router %s unreachable for live-sessions", pk)
            reachable = False
            sessions = []
        except Exception:
            logger.exception("Unexpected error fetching live sessions for router %s", pk)
            reachable = False
            sessions = []

        pppoe_count = sum(1 for s in sessions if s['type'] == 'pppoe')
        hotspot_count = sum(1 for s in sessions if s['type'] == 'hotspot')

        return Response({
            'router_id': router.id,
            'reachable': reachable,
            'sessions': sessions,
            'counts': {
                'pppoe': pppoe_count,
                'hotspot': hotspot_count,
                'total': len(sessions),
            },
        })
