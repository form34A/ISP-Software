"""
Synchronous payment -> subscription activation -> router provisioning.

This is the one place a completed M-Pesa (or other gateway) Transaction turns
into a live, connected hotspot/PPPoE user. It's called directly from the
payment callback view - no Celery, no HTTP self-call into another view, no
queue. There is no worker process running in this deployment, so "activate
the subscription" has to happen inline in the request that confirms payment.

On provisioning failure, the Subscription is left in 'pending_activation'
(retryable by the `reconcile_payments` management command) - the Transaction
itself is never touched by this module, so the fact that money was received
is never lost regardless of what happens here.
"""

import concurrent.futures
import logging
import re

from django.core.cache import cache
from django.db import transaction as db_transaction
from django.utils import timezone

from service_operations.models.subscription_models import Subscription
from service_operations.notifications import notify, NotificationEvent

logger = logging.getLogger(__name__)

# Bound for activate_and_provision_bounded() below - how long a caller with a
# live request waiting (the poll-driven retry in captive_portal.PortalStatusView)
# will block on a router that's slow or unreachable, e.g. a dead SSH tunnel.
BOUNDED_RETRY_TIMEOUT_SECONDS = 8

# Lock TTL for the same helper - comfortably above the worst case a real
# attempt can take (two RouterOS connections, each capped at the connector's
# own 15s socket timeout: profile push + user add), so it always expires on
# its own even if the release in _run_and_release below never runs.
_RETRY_LOCK_TIMEOUT_SECONDS = 30

# RouterOS communication errors echo the *entire failed command* verbatim,
# e.g. .../add =name=... =password=<the actual hotspot/PPPoE secret>
# =profile=... - that plaintext credential must never land in
# Subscription.activation_error (a field an admin UI could plausibly
# surface). Matches RouterOS's "=password=<value>" API word syntax,
# case-insensitive, value ends at the next whitespace.
_SECRET_VALUE_RE = re.compile(r'(?i)(=?\bpassword=)(\S+)')


def _redact_secrets(text):
    """Mask password-like values before they're persisted anywhere - see _SECRET_VALUE_RE."""
    if not text:
        return text
    return _SECRET_VALUE_RE.sub(lambda m: f"{m.group(1)}***REDACTED***", str(text))


def activate_and_provision(payment_transaction):
    """
    payment_transaction: payments.models.Transaction instance, already saved
    with status='completed'.

    Returns (success: bool, error: str|None).
    """
    client = payment_transaction.client
    plan = payment_transaction.plan

    if client is None or plan is None:
        error = "Transaction is missing client or plan; cannot activate a subscription"
        logger.error("activate_and_provision(%s): %s", payment_transaction.reference, error)
        return False, error

    access_type = (payment_transaction.metadata or {}).get('access_type', 'hotspot')

    subscription = payment_transaction.subscription
    if subscription is None:
        subscription = _get_or_create_subscription(payment_transaction, client, plan, access_type)
        payment_transaction.subscription = subscription
        payment_transaction.save(update_fields=['subscription'])

    notify(
        NotificationEvent.PURCHASE_CONFIRMED,
        getattr(client, 'phone_number', None),
        subscription_id=str(subscription.id),
        amount=str(payment_transaction.amount),
        plan_name=getattr(plan, 'name', ''),
        reference=payment_transaction.reference,
    )

    if subscription.access_method == 'pppoe':
        success, error = _activate_pppoe(subscription, payment_transaction, client, plan)
    else:
        success, error = _activate_hotspot(subscription, payment_transaction, client, plan)

    if success:
        notify(
            NotificationEvent.PLAN_ACTIVATED,
            getattr(client, 'phone_number', None),
            subscription_id=str(subscription.id),
            plan_name=getattr(plan, 'name', ''),
        )

    return success, error


def _run_and_release(payment_transaction, lock_key):
    from django.db import connections
    try:
        return activate_and_provision(payment_transaction)
    finally:
        # New thread -> its own DB connection, never reused by the request
        # thread; close it here or it leaks for the life of the process.
        connections.close_all()
        cache.delete(lock_key)


def activate_and_provision_bounded(payment_transaction, timeout_seconds=BOUNDED_RETRY_TIMEOUT_SECONDS):
    """
    Same contract as activate_and_provision (returns (success, error)), but
    never blocks the caller past timeout_seconds - for callers with a live
    HTTP request waiting on the answer (PortalStatusView's poll-driven
    retry), where a slow or unreachable router must not hang the request.

    Runs the real attempt in a background thread and joins it with a
    timeout. If the deadline passes first, this returns (False, 'timeout')
    but the thread keeps running - activate_and_provision's own DB writes
    (subscription/portal_session) are what actually record success, so a
    slow success still lands, just not in time for this particular poll;
    the next poll (or the reconcile_payments sweep) will see it.

    A per-transaction lock (released by the background thread when it
    finishes, not when this function returns) prevents a stranded browser
    polling every few seconds from piling up concurrent connection attempts
    against the same down router. If a previous attempt for this same
    transaction is still in flight, this returns (False, 'retry_in_progress')
    immediately rather than starting another one.
    """
    lock_key = f"activate_and_provision_bounded:{payment_transaction.id}"
    if not cache.add(lock_key, "1", timeout=_RETRY_LOCK_TIMEOUT_SECONDS):
        return False, "retry_in_progress"

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_run_and_release, payment_transaction, lock_key)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            logger.warning(
                "activate_and_provision_bounded: timed out after %ss for transaction %s "
                "(router likely unreachable) - continuing in background",
                timeout_seconds, payment_transaction.reference,
            )
            return False, "timeout"
        except Exception as e:
            logger.exception(
                "activate_and_provision_bounded: raised for transaction %s", payment_transaction.reference
            )
            cache.delete(lock_key)
            return False, str(e)
    finally:
        # wait=False: never block this request on the background thread -
        # that would defeat the entire point of bounding the wait above.
        executor.shutdown(wait=False)


def _get_or_create_subscription(payment_transaction, client, plan, access_type):
    access_method = 'pppoe' if access_type == 'pppoe' else 'hotspot'
    client_type = 'pppoe_client' if access_method == 'pppoe' else 'hotspot_client'

    duration_hours = _plan_duration_hours(plan)
    end_date = timezone.now() + timezone.timedelta(hours=duration_hours) if duration_hours else None

    subscription = Subscription.objects.create(
        client_id=client.id,
        internet_plan_id=plan.id,
        client_type=client_type,
        access_method=access_method,
        status='pending_activation',
        payment_reference=payment_transaction.reference,
        payment_method='mpesa',
        payment_confirmed_at=timezone.now(),
        end_date=end_date,
    )
    logger.info(
        "Created subscription %s for transaction %s (client=%s, plan=%s)",
        subscription.id, payment_transaction.reference, client.id, plan.id,
    )
    return subscription


def _plan_duration_hours(plan):
    """
    Hours until this plan's Subscription should expire, or None for no
    expiry.

    Source: plan.get_technical_config('hotspot') - which returns
    'validity_period' (the bare value, e.g. "2") and 'validity_unit'
    (e.g. "Hours") as two separate keys, not a nested {value, unit} pair
    (see InternetPlan.get_technical_config). Reading plan.expiry_value/
    plan.expiry_unit directly (the old code here) always returned None
    because those attributes don't exist on InternetPlan - end_date was
    never being set.

    'unlimited' (case-insensitive, in either the value or the unit) means
    no expiry - the same convention internet_plans.utils.formatters/
    validators use for every other value/unit pair on a plan (data_limit,
    usage_limit, speeds, ...).
    """
    if plan is None:
        return None

    config = plan.get_technical_config('hotspot')
    value = config.get('validity_period')
    unit = config.get('validity_unit')

    if value is None or unit is None:
        return None
    if str(value).strip().lower() == 'unlimited' or str(unit).strip().lower() == 'unlimited':
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    unit_normalized = str(unit).strip().lower()
    if unit_normalized.startswith('minute'):
        return numeric_value / 60
    if unit_normalized.startswith('hour'):
        return numeric_value
    if unit_normalized.startswith('day'):
        return numeric_value * 24
    return None


def _resolve_portal_session(payment_transaction):
    from network_management.models.portal_session_model import PortalSession

    portal_session_id = (payment_transaction.metadata or {}).get('portal_session_id')
    if portal_session_id:
        portal_session = PortalSession.objects.filter(id=portal_session_id).first()
        if portal_session:
            return portal_session

    return PortalSession.objects.filter(transaction=payment_transaction).order_by('-created_at').first()


def _activate_hotspot(subscription, payment_transaction, client, plan):
    from network_management.services.hotspot_provisioning import provision_hotspot_user

    portal_session = _resolve_portal_session(payment_transaction)
    router = portal_session.router if portal_session else None
    mac_address = portal_session.mac_address if portal_session else subscription.hotspot_mac_address

    if not router or not mac_address:
        error = (
            "No router/MAC address known for this transaction (no linked portal "
            "session and none on the subscription); cannot provision a hotspot user."
        )
        _mark_provisioning_failed(subscription, portal_session, error)
        return False, error

    # Self-heal: make sure this plan's /ip/hotspot/user/profile actually
    # exists on *this* router before trying to add a user under it.
    # Confirmed real failure mode: a plan sold whose profile push never
    # landed on a given router provisions fine right up until RouterOS
    # rejects the user add with "input does not match any value of profile".
    # push_plan_profile() is idempotent - a no-op if it's already correct -
    # so this costs nothing on the (normal) case where the profile is fine.
    # Mikrotik-only: it talks RouterOS API directly, and Ubiquiti/Cisco
    # provisioning (see provision_hotspot_user) doesn't use router-side
    # profiles at all.
    if router.type == "mikrotik":
        from network_management.utils.mikrotik_connector import push_plan_profile
        profile_ok, profile_message, _ = push_plan_profile(plan, router)
        if not profile_ok:
            error = f"Could not ensure hotspot profile exists on router: {profile_message}"
            _mark_provisioning_failed(subscription, portal_session, error)
            return False, error

    subscription.hotspot_mac_address = mac_address
    subscription.router_id = router.id

    preferred_username = getattr(client, 'username', None) or f"user_{client.id}"
    username, secret = subscription.ensure_hotspot_credentials(router, preferred_username)

    # Validity is granted from *now* (activation time), not the original
    # purchase time. Subscription.end_date at this point may have been set
    # hours ago at purchase (_get_or_create_subscription) - reusing it here
    # would hand a delayed/retried activation whatever's left of a window
    # that's already expired, even though the customer is only now actually
    # getting online. Recompute fresh and this is also what gets saved below.
    duration_hours = _plan_duration_hours(plan)
    remaining_time = int(duration_hours * 3600) if duration_hours else 0
    success, error = provision_hotspot_user(
        router, mac_address, username, secret, plan=plan, remaining_time=max(0, remaining_time),
        subscription_id=str(subscription.id),
    )

    if success:
        end_date = timezone.now() + timezone.timedelta(hours=duration_hours) if duration_hours else None
        with db_transaction.atomic():
            subscription.status = 'active'
            subscription.activation_successful = True
            subscription.activation_completed_at = timezone.now()
            subscription.activation_error = None
            subscription.end_date = end_date
            subscription.save(update_fields=[
                'status', 'activation_successful', 'activation_completed_at',
                'activation_error', 'hotspot_mac_address', 'router_id', 'end_date', 'updated_at',
            ])
            if portal_session:
                portal_session.status = 'activated'
                portal_session.save(update_fields=['status', 'updated_at'])
        return True, None

    _mark_provisioning_failed(subscription, portal_session, error)
    return False, error


def _activate_pppoe(subscription, payment_transaction, client, plan):
    from network_management.services.hotspot_provisioning import provision_pppoe_user
    from network_management.models.router_management_model import Router

    portal_session = _resolve_portal_session(payment_transaction)
    router = None
    if subscription.router_id:
        router = Router.objects.filter(id=subscription.router_id).first()
    if router is None and portal_session:
        router = portal_session.router

    if not router:
        error = "No router known for this PPPoE subscription; cannot provision."
        _mark_provisioning_failed(subscription, portal_session, error)
        return False, error

    # Self-heal, PPPoE equivalent of _activate_hotspot's push_plan_profile()
    # call above - /ppp/secret's profile= is validated against /ppp/profile
    # existing on the router the exact same way /ip/hotspot/user's is.
    if router.type == "mikrotik":
        from network_management.utils.mikrotik_connector import push_pppoe_profile
        profile_ok, profile_message, _ = push_pppoe_profile(plan, router)
        if not profile_ok:
            error = f"Could not ensure PPPoE profile exists on router: {profile_message}"
            _mark_provisioning_failed(subscription, portal_session, error)
            return False, error

    # Same "grant from activation time, not purchase time" reasoning as
    # _activate_hotspot above.
    duration_hours = _plan_duration_hours(plan)
    remaining_time = int(duration_hours * 3600) if duration_hours else 0
    success, error = provision_pppoe_user(
        router, subscription.pppoe_username, subscription.pppoe_password,
        plan=plan, remaining_time=max(0, remaining_time)
    )

    if success:
        end_date = timezone.now() + timezone.timedelta(hours=duration_hours) if duration_hours else None
        with db_transaction.atomic():
            subscription.status = 'active'
            subscription.activation_successful = True
            subscription.activation_completed_at = timezone.now()
            subscription.activation_error = None
            subscription.router_id = router.id
            subscription.end_date = end_date
            subscription.save(update_fields=[
                'status', 'activation_successful', 'activation_completed_at',
                'activation_error', 'router_id', 'end_date', 'updated_at',
            ])
            if portal_session:
                portal_session.status = 'activated'
                portal_session.save(update_fields=['status', 'updated_at'])
        return True, None

    _mark_provisioning_failed(subscription, portal_session, error)
    return False, error


def _mark_provisioning_failed(subscription, portal_session, error):
    """
    Leave the subscription retryable rather than marking it failed outright -
    the payment already succeeded, so this must stay something the
    reconciliation job can pick back up, not a dead end.
    """
    subscription.status = 'pending_activation'
    subscription.activation_successful = False
    # The full, unredacted error still goes to the server log below (an
    # internal-only, access-controlled destination) - only what's persisted
    # on the model itself is scrubbed, since that field is plausibly
    # surfaced through an admin UI/API response.
    subscription.activation_error = _redact_secrets(error)
    subscription.activation_attempts = (subscription.activation_attempts or 0) + 1
    subscription.save(update_fields=[
        'status', 'activation_successful', 'activation_error', 'activation_attempts', 'updated_at',
    ])
    logger.error("Provisioning failed for subscription %s: %s", subscription.id, error)
    if portal_session:
        portal_session.status = 'provisioning_failed'
        portal_session.save(update_fields=['status', 'updated_at'])
