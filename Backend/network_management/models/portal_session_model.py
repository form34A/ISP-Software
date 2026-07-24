"""
Portal Session - the record that carries a customer from the MikroTik hotspot
redirect through phone capture, payment, and activation.

MikroTik's walled-garden login page redirect passes several query parameters
(mac, ip, link-login-only, link-orig, ...) that a captive-portal page needs in
order to eventually log the client into the router. This model is where those
parameters are captured and kept, along with everything the portal learns
about the visitor afterwards (phone number, subscription, transaction), so the
session survives the user closing and reopening the browser tab - it's looked
up by router + MAC address, not by anything client-side like a cookie.
"""

import uuid

from django.db import models
from django.utils import timezone


class PortalSession(models.Model):
    STATUS_CHOICES = (
        ("landed", "Landed on portal"),
        ("phone_captured", "Phone number captured"),
        ("plan_selected", "Plan selected"),
        ("payment_pending", "Payment initiated, awaiting callback"),
        ("payment_failed", "Payment failed"),
        ("activated", "Subscription activated"),
        ("provisioning_failed", "Payment received but router provisioning failed"),
        ("connected", "Logged into the router"),
        ("abandoned", "Abandoned/expired"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- What MikroTik handed us on the walled-garden redirect ---
    router = models.ForeignKey(
        "network_management.Router",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_sessions",
        help_text="Router that redirected this client to the portal.",
    )
    site = models.CharField(
        max_length=100,
        blank=True,
        help_text=(
            "Site label, snapshotted from Router.location at creation time. "
            "There is no separate Site model in this codebase yet - this is a "
            "denormalized copy so historical sessions don't drift if the "
            "router's location field changes later."
        ),
    )
    mac_address = models.CharField(max_length=17, db_index=True, help_text="MikroTik 'mac' param")
    client_ip = models.GenericIPAddressField(null=True, blank=True, help_text="MikroTik 'ip' param")
    link_login_url = models.URLField(
        max_length=1000,
        blank=True,
        help_text="MikroTik 'link-login-only' param - where the portal POSTs credentials back to the router.",
    )
    link_orig_url = models.URLField(
        max_length=1000,
        blank=True,
        help_text="MikroTik 'link-orig' param - the destination the client originally requested.",
    )

    # --- What the portal learns about the visitor afterwards ---
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    client = models.ForeignKey(
        "authentication.UserAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_sessions",
        limit_choices_to={"user_type": "client"},
    )
    subscription = models.ForeignKey(
        "service_operations.Subscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_sessions",
    )
    transaction = models.ForeignKey(
        "payments.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_sessions",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="landed", db_index=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(
        default=timezone.now,
        help_text="Bumped whenever the portal re-fetches this session, so a closed/reopened tab resumes the same row.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["router", "mac_address"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["mac_address", "status"]),
        ]

    def __str__(self):
        return f"PortalSession {self.id} ({self.mac_address}) - {self.get_status_display()}"

    @classmethod
    def get_resumable(cls, router_id, mac_address):
        """
        Find the most recent non-terminal session for this router+mac, so a
        client who closes and reopens the portal page picks up where they
        left off instead of starting a new session.
        """
        return (
            cls.objects.filter(router_id=router_id, mac_address=mac_address)
            .exclude(status__in=["abandoned", "connected"])
            .order_by("-created_at")
            .first()
        )

    def touch(self):
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at"])
