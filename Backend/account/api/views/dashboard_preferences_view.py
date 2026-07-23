"""
account/api/views/dashboard_preferences_view.py

Per-user Dashboard card/chart visibility preferences, stored under the
"dashboard" namespace inside UserAccount.metadata so it doesn't clobber any
other feature that shares that same JSON blob.
"""

import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from account.dashboard_prefs import (
    is_valid_dashboard_pref_key, get_available_dashboard_items, MAX_HIDDEN_ITEMS
)

logger = logging.getLogger(__name__)


class DashboardPreferencesView(APIView):
    """
    GET   -> {"hidden": [...], "available": [...]}  (current user's hidden
             dashboard cards/charts, plus every toggleable item's label/group
             so the frontend never hardcodes them)
    PATCH -> {"hidden": [...]}  (replace the hidden list; validated)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        dashboard_prefs = (request.user.metadata or {}).get("dashboard", {})
        return Response({
            "hidden": dashboard_prefs.get("hidden", []),
            "available": get_available_dashboard_items(),
        })

    def patch(self, request):
        if "hidden" not in request.data:
            return Response(
                {"detail": "'hidden' is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        hidden = request.data["hidden"]

        if not isinstance(hidden, list):
            return Response(
                {"detail": "'hidden' must be a list"}, status=status.HTTP_400_BAD_REQUEST
            )

        if len(hidden) > MAX_HIDDEN_ITEMS:
            return Response(
                {"detail": f"'hidden' cannot have more than {MAX_HIDDEN_ITEMS} entries"},
                status=status.HTTP_400_BAD_REQUEST
            )

        invalid = [key for key in hidden if not is_valid_dashboard_pref_key(key)]
        if invalid:
            return Response(
                {"detail": "Unknown dashboard preference key(s)", "invalid": invalid},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = request.user
            metadata = user.metadata or {}
            dashboard_prefs = metadata.get("dashboard", {})
            dashboard_prefs["hidden"] = hidden
            metadata["dashboard"] = dashboard_prefs
            user.metadata = metadata
            user.save(update_fields=["metadata"])
        except Exception as e:
            logger.error(f"Failed to save dashboard preferences: {e}", exc_info=True)
            return Response(
                {"detail": "Failed to save dashboard preferences"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({"hidden": hidden})
