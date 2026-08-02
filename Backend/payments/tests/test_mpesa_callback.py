"""
Tests for the M-Pesa callback path (payments.api.views.payment_config_view.MpesaCallbackView)
and the synchronous activation it triggers (service_operations.services.payment_activation).

Router calls are always mocked at the provisioning boundary
(network_management.services.hotspot_provisioning.provision_hotspot_user) -
no test in this file opens, or can open, a connection to a real device.

NOTE: these tests were written without a Django environment available to run
them in (no `django` package installed in the sandbox this was authored in).
Run `python manage.py test payments.tests.test_mpesa_callback` before relying
on them - a live DB and Redis (per docker-compose) are required, same as any
other test in this project.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import UserAccount
from internet_plans.models.plan_models import InternetPlan
from network_management.models.portal_session_model import PortalSession
from network_management.models.router_management_model import Router
from payments.models.payment_config_model import PaymentGateway, Transaction
from service_operations.models.subscription_models import Subscription

CALLBACK_URL = "/api/payments/callback/mpesa/"
PROVISION_TARGET = "network_management.services.hotspot_provisioning.provision_hotspot_user"


def stk_callback(checkout_id, result_code=0, result_desc="The service request is processed successfully.",
                  amount=None, receipt="NLJ7RT61SV", phone="254712345678"):
    stk_callback_body = {
        "MerchantRequestID": "29115-34620561-1",
        "CheckoutRequestID": checkout_id,
        "ResultCode": result_code,
        "ResultDesc": result_desc,
    }
    if result_code == 0:
        stk_callback_body["CallbackMetadata"] = {
            "Item": [
                {"Name": "Amount", "Value": amount},
                {"Name": "MpesaReceiptNumber", "Value": receipt},
                {"Name": "TransactionDate", "Value": 20260724120000},
                {"Name": "PhoneNumber", "Value": phone},
            ]
        }
    return {"Body": {"stkCallback": stk_callback_body}}


class MpesaCallbackTestBase(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.user = UserAccount.objects.create_client_user(
            phone_number="+254712345678",
            connection_type="hotspot",
            source="captive_portal",
        )
        self.gateway = PaymentGateway.objects.create(
            name="mpesa_paybill", is_active=True, sandbox_mode=True,
        )
        self.plan = InternetPlan.objects.create(name="Reconciliation Test Plan", price=Decimal("50.00"))
        self.router = Router.objects.create(
            name="Test Router", ip="10.0.0.1", type="mikrotik",
            status="connected", manages_hotspot_users=True,
        )

    def make_transaction(self, checkout_id, amount=Decimal("50.00"), with_portal_session=True):
        txn = Transaction.objects.create(
            client=self.user,
            gateway=self.gateway,
            plan=self.plan,
            amount=amount,
            status="pending",
            checkout_request_id=checkout_id,
            metadata={"access_type": "hotspot"},
        )
        if with_portal_session:
            PortalSession.objects.create(
                router=self.router,
                mac_address="AA:BB:CC:DD:EE:FF",
                transaction=txn,
            )
        return txn

    def post_callback(self, payload):
        # Callback arrives over HTTPS in production (via the Cloudflare tunnel,
        # X-Forwarded-Proto: https), and SECURE_SSL_REDIRECT would 301 a plain
        # HTTP request before it ever reaches the view.
        return self.api.post(CALLBACK_URL, payload, format="json", secure=True)


class ValidCallbackTests(MpesaCallbackTestBase):
    @patch(PROVISION_TARGET)
    def test_valid_callback_completes_transaction_and_activates_subscription(self, mock_provision):
        mock_provision.return_value = (True, None)
        txn = self.make_transaction("ws_CO_valid_1")

        response = self.post_callback(stk_callback("ws_CO_valid_1", result_code=0, amount="50"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ResultCode"], 0)

        txn.refresh_from_db()
        self.assertEqual(txn.status, "completed")
        self.assertIsNotNone(txn.subscription)
        self.assertEqual(txn.subscription.status, "active")
        self.assertTrue(txn.subscription.activation_successful)
        self.assertTrue(txn.subscription.hotspot_password)  # random secret was generated
        mock_provision.assert_called_once()
        # Regression lock: multiple signal handlers + the explicit callback-view
        # call all race to log this completion - exactly one row must survive.
        self.assertEqual(txn.logs.count(), 1)

    @patch(PROVISION_TARGET)
    def test_replayed_callback_does_not_double_activate(self, mock_provision):
        mock_provision.return_value = (True, None)
        txn = self.make_transaction("ws_CO_replay_1")
        payload = stk_callback("ws_CO_replay_1", result_code=0, amount="50")

        first = self.post_callback(payload)
        second = self.post_callback(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["ResultDesc"], "Already processed")

        # Provisioning (and therefore subscription creation) only happened once.
        mock_provision.assert_called_once()
        txn.refresh_from_db()
        self.assertEqual(txn.status, "completed")
        self.assertEqual(Subscription.objects.filter(payment_reference=txn.reference).count(), 1)
        # Regression lock: replaying the callback must not create a second log either.
        self.assertEqual(txn.logs.count(), 1)


class RejectionTests(MpesaCallbackTestBase):
    @patch(PROVISION_TARGET)
    def test_unknown_checkout_id_is_rejected(self, mock_provision):
        response = self.post_callback(stk_callback("ws_CO_never_initiated", result_code=0, amount="50"))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["ResultCode"], 1)
        mock_provision.assert_not_called()

    @patch(PROVISION_TARGET)
    def test_amount_mismatch_is_rejected(self, mock_provision):
        txn = self.make_transaction("ws_CO_mismatch_1", amount=Decimal("50.00"))

        response = self.post_callback(stk_callback("ws_CO_mismatch_1", result_code=0, amount="10"))

        self.assertEqual(response.status_code, 400)
        txn.refresh_from_db()
        self.assertEqual(txn.status, "failed")
        self.assertEqual(txn.failure_reason, "amount_mismatch")
        self.assertIsNone(txn.subscription)
        mock_provision.assert_not_called()


class FailureResultCodeTests(MpesaCallbackTestBase):
    @patch(PROVISION_TARGET)
    def test_cancelled_by_user(self, mock_provision):
        txn = self.make_transaction("ws_CO_cancel_1")
        response = self.post_callback(
            stk_callback("ws_CO_cancel_1", result_code=1032, result_desc="Request cancelled by user")
        )
        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, "cancelled")
        self.assertEqual(txn.failure_reason, "cancelled_by_user")
        mock_provision.assert_not_called()

    @patch(PROVISION_TARGET)
    def test_insufficient_funds(self, mock_provision):
        txn = self.make_transaction("ws_CO_funds_1")
        response = self.post_callback(
            stk_callback("ws_CO_funds_1", result_code=1, result_desc="The balance is insufficient for the transaction")
        )
        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, "failed")
        self.assertEqual(txn.failure_reason, "insufficient_funds")
        mock_provision.assert_not_called()

    @patch(PROVISION_TARGET)
    def test_timeout(self, mock_provision):
        txn = self.make_transaction("ws_CO_timeout_1")
        response = self.post_callback(
            stk_callback("ws_CO_timeout_1", result_code=1037, result_desc="DS timeout user cannot be reached")
        )
        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, "failed")
        self.assertEqual(txn.failure_reason, "timeout")
        mock_provision.assert_not_called()

    @patch(PROVISION_TARGET)
    def test_wrong_pin(self, mock_provision):
        txn = self.make_transaction("ws_CO_pin_1")
        response = self.post_callback(
            stk_callback("ws_CO_pin_1", result_code=2001, result_desc="Wrong PIN entered")
        )
        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, "failed")
        self.assertEqual(txn.failure_reason, "wrong_pin")
        mock_provision.assert_not_called()

    @patch(PROVISION_TARGET)
    def test_replayed_failure_callback_is_also_idempotent(self, mock_provision):
        txn = self.make_transaction("ws_CO_replay_fail_1")
        payload = stk_callback("ws_CO_replay_fail_1", result_code=1032, result_desc="Request cancelled by user")

        self.post_callback(payload)
        second = self.post_callback(payload)

        self.assertEqual(second.json()["ResultDesc"], "Already processed")
        txn.refresh_from_db()
        self.assertEqual(txn.status, "cancelled")
        mock_provision.assert_not_called()


class ProvisioningFailureTests(MpesaCallbackTestBase):
    @patch(PROVISION_TARGET)
    def test_provisioning_failure_keeps_money_recorded_and_leaves_subscription_retryable(self, mock_provision):
        mock_provision.return_value = (False, "Router unreachable: connection timed out")
        txn = self.make_transaction("ws_CO_provfail_1")

        response = self.post_callback(stk_callback("ws_CO_provfail_1", result_code=0, amount="50"))

        # Safaricom still gets acked - the payment itself succeeded and must
        # not be redelivered/retried by Safaricom just because provisioning failed.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ResultCode"], 0)

        txn.refresh_from_db()
        self.assertEqual(txn.status, "completed", "money received must never be lost/reverted")
        self.assertIsNotNone(txn.subscription)

        subscription = txn.subscription
        self.assertEqual(subscription.status, "pending_activation", "must stay retryable by reconcile_payments")
        self.assertFalse(subscription.activation_successful)
        self.assertIn("Router unreachable", subscription.activation_error)
        self.assertEqual(subscription.activation_attempts, 1)

    @patch(PROVISION_TARGET)
    def test_missing_portal_session_fails_clearly_without_losing_payment(self, mock_provision):
        txn = self.make_transaction("ws_CO_nomac_1", with_portal_session=False)

        response = self.post_callback(stk_callback("ws_CO_nomac_1", result_code=0, amount="50"))

        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, "completed")
        self.assertEqual(txn.subscription.status, "pending_activation")
        mock_provision.assert_not_called()
