"""
Reconciliation for the M-Pesa payment -> activation spine. Two independent
sweeps, both safe to run repeatedly (idempotent - see below):

1. Stale pending transactions: an STK push was sent, we have a
   checkout_request_id, but no callback arrived within --stale-minutes
   (Safaricom's callback can fail to be delivered - network issues, tunnel
   down, etc). We query Safaricom directly for the real status and resolve
   the transaction the same way a callback would have.

2. Unprovisioned paid subscriptions: the transaction completed but router
   provisioning failed (or was never attempted) - retries activation for
   any subscription still sitting in 'pending_activation' with a completed
   payment behind it.

Intended to run from cron on an interval, in the same spirit as sample_wan.py
in network_management - this command does not install its own cron entry.

Idempotency: transaction resolution takes the same select_for_update +
terminal-status-check path MpesaCallbackView uses, so a transaction that
gets a real callback in between two runs of this command (or is queried
twice due to overlapping cron runs) is only ever resolved once. Subscription
retries only touch subscriptions still in 'pending_activation', so a
successful retry removes it from the next sweep automatically.
"""

import base64
import logging
from datetime import datetime, timedelta

import requests
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from payments.models.payment_config_model import Transaction
from service_operations.models.subscription_models import Subscription

logger = logging.getLogger(__name__)

# Same well-known Safaricom Daraja STK push ResultCodes used by the callback
# view (payments.api.views.payment_config_view.MpesaCallbackView).
FAILURE_REASON_BY_RESULT_CODE = {
    1: 'insufficient_funds',
    1032: 'cancelled_by_user',
    1037: 'timeout',
    2001: 'wrong_pin',
}


class Command(BaseCommand):
    help = (
        "Reconcile M-Pesa payments: query Safaricom for stale pending transactions "
        "with no callback, and retry router provisioning for paid subscriptions "
        "that never got activated."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--stale-minutes', type=int, default=10,
            help="How old a pending transaction must be before it's queried (default: 10)"
        )
        parser.add_argument('--max-transactions', type=int, default=50)
        parser.add_argument('--max-subscriptions', type=int, default=50)
        parser.add_argument('--skip-transactions', action='store_true', help="Skip the stale-transaction sweep")
        parser.add_argument('--skip-subscriptions', action='store_true', help="Skip the unprovisioned-subscription sweep")

    def handle(self, *args, **options):
        if not options['skip_transactions']:
            self._reconcile_stale_transactions(options['stale_minutes'], options['max_transactions'])
        if not options['skip_subscriptions']:
            self._retry_unprovisioned_subscriptions(options['max_subscriptions'])
            self._retry_completed_without_subscription(options['max_subscriptions'])

    # ---- Sweep 1: query Safaricom for transactions with no callback ----

    def _reconcile_stale_transactions(self, stale_minutes, limit):
        cutoff = timezone.now() - timedelta(minutes=stale_minutes)
        stale = list(
            Transaction.objects.filter(
                status='pending',
                checkout_request_id__isnull=False,
                created_at__lte=cutoff,
            ).order_by('created_at')[:limit]
        )

        self.stdout.write(f"Found {len(stale)} stale pending transaction(s) to query")

        for txn in stale:
            try:
                self._reconcile_one_transaction(txn)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Transaction {txn.reference}: reconciliation raised: {e}"))
                logger.exception(f"reconcile_payments: error reconciling transaction {txn.reference}")

    def _reconcile_one_transaction(self, txn):
        gateway = txn.gateway
        if gateway is None:
            self.stderr.write(self.style.WARNING(f"Transaction {txn.reference} has no gateway; skipping"))
            return

        try:
            mpesa_config = gateway.mpesaconfig
        except Exception:
            self.stderr.write(self.style.WARNING(f"Transaction {txn.reference}: gateway has no M-Pesa config; skipping"))
            return

        token = self._generate_mpesa_token(mpesa_config, gateway.sandbox_mode)
        if not token:
            self.stderr.write(self.style.ERROR(f"Transaction {txn.reference}: failed to authenticate with M-Pesa"))
            return

        base_url = "https://sandbox.safaricom.co.ke" if gateway.sandbox_mode else "https://api.safaricom.co.ke"
        password, ts = self._generate_password(mpesa_config)
        payload = {
            "BusinessShortCode": mpesa_config.short_code,
            "Password": password,
            "Timestamp": ts,
            "CheckoutRequestID": txn.checkout_request_id,
        }

        try:
            response = requests.post(
                f"{base_url}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30,
            ).json()
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Transaction {txn.reference}: query request failed: {e}"))
            return

        try:
            result_code = int(response.get('ResultCode'))
        except (TypeError, ValueError):
            # Safaricom returns a non-numeric ResultCode (or an errorCode
            # envelope) while the push is still awaiting user action -
            # nothing to resolve yet, try again next run.
            self.stdout.write(
                f"Transaction {txn.reference}: not resolved yet "
                f"({response.get('errorMessage') or response.get('ResultDesc') or response})"
            )
            return

        self._apply_query_result(txn, result_code, response)

    def _apply_query_result(self, txn, result_code, response):
        with db_transaction.atomic():
            txn = Transaction.objects.select_for_update().get(pk=txn.pk)

            # Idempotency: if a real callback (or an earlier reconciliation
            # run) already resolved this transaction, there's nothing to do.
            if txn.status in ('completed', 'failed', 'cancelled', 'refunded'):
                self.stdout.write(f"Transaction {txn.reference}: already {txn.status}, skipping")
                return

            if result_code == 0:
                txn.status = 'completed'
                txn.failure_reason = None
                txn.metadata.update({
                    'reconciled_via': 'stkpushquery',
                    'reconciled_at': timezone.now().isoformat(),
                    'stkpushquery_response': response,
                })
                txn.save()

                if not txn.logs.exists():
                    txn.create_transaction_log(status='success', access_type=(txn.metadata or {}).get('access_type', 'hotspot'))
                else:
                    for log in txn.logs.all():
                        log.status = 'success'
                        log.save()

                self.stdout.write(self.style.SUCCESS(f"Transaction {txn.reference}: confirmed paid via query, activating"))
            else:
                reason = FAILURE_REASON_BY_RESULT_CODE.get(result_code, 'other')
                txn.status = 'cancelled' if reason == 'cancelled_by_user' else 'failed'
                txn.failure_reason = reason
                txn.metadata.update({
                    'reconciled_via': 'stkpushquery',
                    'reconciled_at': timezone.now().isoformat(),
                    'mpesa_result_code': result_code,
                    'stkpushquery_response': response,
                })
                txn.save()
                self.stdout.write(f"Transaction {txn.reference}: resolved as {txn.status} ({reason}) via query")
                return

        # Activation happens outside the row lock, same as the callback view.
        from service_operations.services.payment_activation import activate_and_provision
        try:
            success, error = activate_and_provision(txn)
        except Exception as e:
            logger.exception(f"reconcile_payments: activation raised for {txn.reference}")
            success, error = False, str(e)

        if success:
            self.stdout.write(self.style.SUCCESS(f"Transaction {txn.reference}: provisioned successfully"))
        else:
            self.stderr.write(self.style.WARNING(f"Transaction {txn.reference}: payment confirmed but provisioning failed: {error}"))

    def _generate_mpesa_token(self, mpesa_config, sandbox_mode):
        try:
            credentials = f"{mpesa_config.consumer_key}:{mpesa_config.consumer_secret}"
            encoded = base64.b64encode(credentials.encode()).decode()
            base_url = "https://sandbox.safaricom.co.ke" if sandbox_mode else "https://api.safaricom.co.ke"
            response = requests.get(
                f"{base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": f"Basic {encoded}"},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json().get('access_token')
            logger.error(f"reconcile_payments: M-Pesa token generation failed: {response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"reconcile_payments: M-Pesa token request failed: {e}")
            return None

    def _generate_password(self, mpesa_config):
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            (mpesa_config.short_code + mpesa_config.passkey + ts).encode()
        ).decode()
        return password, ts

    # ---- Sweep 2: retry provisioning for paid-but-unprovisioned subscriptions ----

    def _retry_unprovisioned_subscriptions(self, limit):
        from service_operations.services.payment_activation import activate_and_provision

        subs = list(
            Subscription.objects.filter(
                status='pending_activation',
                payment_confirmed_at__isnull=False,
                is_active=True,
            ).order_by('created_at')[:limit]
        )

        self.stdout.write(f"Found {len(subs)} unprovisioned paid subscription(s) to retry")

        for sub in subs:
            txn = sub.transactions.filter(status='completed').order_by('-created_at').first()
            if not txn:
                self.stderr.write(self.style.WARNING(
                    f"Subscription {sub.id} is pending_activation with payment_confirmed_at set "
                    f"but has no completed transaction; skipping"
                ))
                continue

            try:
                success, error = activate_and_provision(txn)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Subscription {sub.id}: retry raised: {e}"))
                logger.exception(f"reconcile_payments: retry raised for subscription {sub.id}")
                continue

            if success:
                self.stdout.write(self.style.SUCCESS(f"Subscription {sub.id}: provisioned successfully"))
            else:
                self.stderr.write(self.style.WARNING(f"Subscription {sub.id}: still failing: {error}"))

    # ---- Sweep 3: completed payments that never got a subscription at all ----

    def _retry_completed_without_subscription(self, limit):
        """
        Sweep 2 above only looks at Subscriptions already in pending_activation -
        it can never find a Transaction that completed but activate_and_provision
        never created a Subscription for at all (e.g. client/plan went missing,
        or subscription creation itself raised). This sweep is what makes those
        findable and retryable instead of silently stuck.
        """
        from service_operations.services.payment_activation import activate_and_provision

        txns = list(
            Transaction.objects.filter(
                status='completed',
                subscription__isnull=True,
            ).order_by('created_at')[:limit]
        )

        self.stdout.write(f"Found {len(txns)} completed transaction(s) with no subscription to retry")

        for txn in txns:
            try:
                success, error = activate_and_provision(txn)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Transaction {txn.reference}: retry raised: {e}"))
                logger.exception(f"reconcile_payments: retry raised for transaction {txn.reference}")
                continue

            if success:
                self.stdout.write(self.style.SUCCESS(f"Transaction {txn.reference}: subscription created and provisioned"))
            else:
                self.stderr.write(self.style.WARNING(f"Transaction {txn.reference}: still failing: {error}"))
