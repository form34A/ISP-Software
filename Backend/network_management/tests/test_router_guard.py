"""
Tests for the router safety gate (network_management.utils.router_guard) and
its enforcement in network_management.services.hotspot_provisioning.

These confirm the gate refuses (rather than silently no-oping or crashing)
when a router isn't marked manages_hotspot_users, and that a router with the
flag off never reaches the point of importing/calling routeros_api at all -
no test here can open a connection to a real device.

NOTE: written without a Django environment available to execute it in - run
`python manage.py test network_management.tests.test_router_guard` before
relying on it.
"""

from unittest.mock import patch

from django.test import TestCase

from network_management.models.router_management_model import Router
from network_management.services.hotspot_provisioning import provision_hotspot_user, provision_pppoe_user
from network_management.utils.router_guard import RouterNotManagedError, ensure_router_manages_hotspot_users


class RouterGuardTests(TestCase):
    def setUp(self):
        self.unmanaged_router = Router.objects.create(
            name="Unmanaged Router", ip="10.0.0.2", type="mikrotik", status="connected",
        )
        self.managed_router = Router.objects.create(
            name="Managed Router", ip="10.0.0.3", type="mikrotik", status="connected",
            manages_hotspot_users=True,
        )

    def test_new_router_defaults_to_unmanaged(self):
        fresh = Router.objects.create(name="Fresh Router", ip="10.0.0.4")
        self.assertFalse(fresh.manages_hotspot_users)

    def test_guard_raises_for_unmanaged_router(self):
        with self.assertRaises(RouterNotManagedError):
            ensure_router_manages_hotspot_users(self.unmanaged_router, "test action")

    def test_guard_passes_for_managed_router(self):
        # Should not raise.
        ensure_router_manages_hotspot_users(self.managed_router, "test action")

    @patch("routeros_api.RouterOsApiPool")
    def test_provision_hotspot_user_refuses_without_touching_routeros(self, mock_pool):
        success, error = provision_hotspot_user(
            self.unmanaged_router, "AA:BB:CC:DD:EE:FF", "someuser", "somesecret"
        )
        self.assertFalse(success)
        self.assertIn("manages_hotspot_users", error)
        mock_pool.assert_not_called()

    @patch("routeros_api.RouterOsApiPool")
    def test_provision_pppoe_user_refuses_without_touching_routeros(self, mock_pool):
        success, error = provision_pppoe_user(
            self.unmanaged_router, "someuser", "somesecret"
        )
        self.assertFalse(success)
        self.assertIn("manages_hotspot_users", error)
        mock_pool.assert_not_called()

    @patch("routeros_api.RouterOsApiPool")
    def test_provision_hotspot_user_proceeds_when_managed(self, mock_pool_cls):
        mock_api = mock_pool_cls.return_value.get_api.return_value
        mock_api.get_resource.return_value.get.return_value = []

        success, error = provision_hotspot_user(
            self.managed_router, "AA:BB:CC:DD:EE:FF", "someuser", "somesecret"
        )

        self.assertTrue(success, error)
        mock_pool_cls.return_value.disconnect.assert_called_once()
