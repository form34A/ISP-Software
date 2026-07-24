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

import logging

from django.db import transaction as db_transaction
from django.utils import timezone

from service_operations.models.subscription_models import Subscription
from service_operations.notifications import notify, NotificationEvent

logger = logging.getLogger(__name__)


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
    expiry_value = getattr(plan, "expiry_value", None)
    expiry_unit = getattr(plan, "expiry_unit", None)
    if not expiry_value or not expiry_unit:
        return None
    try:
        value = int(expiry_value)
    except (TypeError, ValueError):
        return None
    if expiry_unit == 'Hours':
        return value
    if expiry_unit == 'Days':
        return value * 24
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

    subscription.hotspot_mac_address = mac_address
    subscription.router_id = router.id

    preferred_username = getattr(client, 'username', None) or f"user_{client.id}"
    username, secret = subscription.ensure_hotspot_credentials(router, preferred_username)

    remaining_time = int((subscription.end_date - timezone.now()).total_seconds()) if subscription.end_date else 0
    success, error = provision_hotspot_user(
        router, mac_address, username, secret, plan=plan, remaining_time=max(0, remaining_time)
    )

    if success:
        with db_transaction.atomic():
            subscription.status = 'active'
            subscription.activation_successful = True
            subscription.activation_completed_at = timezone.now()
            subscription.activation_error = None
            subscription.save(update_fields=[
                'status', 'activation_successful', 'activation_completed_at',
                'activation_error', 'hotspot_mac_address', 'router_id', 'updated_at',
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

    remaining_time = int((subscription.end_date - timezone.now()).total_seconds()) if subscription.end_date else 0
    success, error = provision_pppoe_user(
        router, subscription.pppoe_username, subscription.pppoe_password,
        plan=plan, remaining_time=max(0, remaining_time)
    )

    if success:
        with db_transaction.atomic():
            subscription.status = 'active'
            subscription.activation_successful = True
            subscription.activation_completed_at = timezone.now()
            subscription.activation_error = None
            subscription.router_id = router.id
            subscription.save(update_fields=[
                'status', 'activation_successful', 'activation_completed_at',
                'activation_error', 'router_id', 'updated_at',
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
    subscription.activation_error = error
    subscription.activation_attempts = (subscription.activation_attempts or 0) + 1
    subscription.save(update_fields=[
        'status', 'activation_successful', 'activation_error', 'activation_attempts', 'updated_at',
    ])
    logger.error("Provisioning failed for subscription %s: %s", subscription.id, error)
    if portal_session:
        portal_session.status = 'provisioning_failed'
        portal_session.save(update_fields=['status', 'updated_at'])
