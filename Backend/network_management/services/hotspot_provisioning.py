"""
Shared RouterOS-writing logic for putting a hotspot/PPPoE user onto a router.

This is the single place that actually talks to a router to create a hotspot
or PPPoE user. It's used both by the admin-triggered activation endpoint
(RouterActivateUserView) and by the payment-triggered synchronous provisioning
path (payments.api.views.payment_config_view.MpesaCallbackView), so there is
exactly one implementation of "how do we add a user to a router" and exactly
one place the manages_hotspot_users safety gate is enforced.

Credentials (username/secret) are passed in rather than derived here - see
service_operations.models.subscription_models.Subscription.ensure_hotspot_credentials
and the inline generation in RouterActivateUserView for the two call sites.
"""

import logging

from routeros_api.api_structure import TimedeltaField

from network_management.utils.router_guard import ensure_router_manages_hotspot_users, RouterNotManagedError

logger = logging.getLogger(__name__)

_DATA_LIMIT_MULTIPLIERS = {
    'b': 1, 'byte': 1, 'bytes': 1,
    'kb': 1024,
    'mb': 1024 ** 2,
    'gb': 1024 ** 3,
    'tb': 1024 ** 4,
}

# Reused to parse RouterOS's own "5h59m4s"-style duration strings back out
# of /ip/hotspot/user's `uptime`/`limit-uptime` fields - same format the
# routeros_api library already parses internally for typed TimedeltaField
# columns, so this borrows its parser rather than re-implementing it.
_TIMEDELTA_FIELD = TimedeltaField()


def _plan_hotspot_raw(plan):
    """
    Raw access_methods['hotspot'] dict, or {}. See
    network_management.utils.mikrotik_connector._plan_hotspot_raw (same
    function, duplicated rather than imported at module scope to avoid a
    circular import - mikrotik_connector is imported locally inside
    functions in this file, never at module level).
    """
    if plan is None:
        return {}
    return (getattr(plan, 'access_methods', None) or {}).get('hotspot') or {}


def _plan_data_limit_bytes(plan):
    """
    Data limit in bytes, from the raw access_methods.hotspot.data_limit
    {'value', 'unit'} pair. Deliberately reads the raw dict rather than
    going through Plan.get_technical_config('hotspot'), which silently
    substitutes {'value': '10', 'unit': 'gb'} for a plan with no
    data_limit configured at all - that masked a genuinely-unconfigured
    plan as a real 10GB cap with no visibility. Missing/unparseable/
    unrecognized here all mean "no cap" (0, RouterOS's own convention for
    unlimited on limit-bytes-total), logged so the gap is visible instead
    of guessed away.
    """
    data_limit = _plan_hotspot_raw(plan).get('data_limit')
    if not isinstance(data_limit, dict) or not data_limit.get('value') or not data_limit.get('unit'):
        logger.warning(
            "Plan %s has no usable data_limit under access_methods.hotspot; provisioning with no data cap.",
            getattr(plan, 'id', 'unknown'),
        )
        return 0

    value = data_limit['value']
    unit = data_limit['unit']

    if str(value).strip().lower() == 'unlimited' or str(unit).strip().lower() == 'unlimited':
        return 0

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        logger.warning(
            "Unparseable data_limit value %r on plan %s; provisioning with no data cap.",
            value, getattr(plan, 'id', 'unknown'),
        )
        return 0

    multiplier = _DATA_LIMIT_MULTIPLIERS.get(str(unit).strip().lower())
    if multiplier is None:
        logger.warning(
            "Unrecognized data_unit %r on plan %s; provisioning with no data cap.",
            unit, getattr(plan, 'id', 'unknown'),
        )
        return 0

    return int(numeric_value * multiplier)


def _parse_routeros_duration_seconds(value):
    """
    Parse a RouterOS duration string (e.g. '5h59m4s', '0s') into whole
    seconds. Returns None for a missing/empty/unparseable value - callers
    treat that as "can't be established honestly", never as 0.
    """
    if not value:
        return None
    try:
        delta = _TIMEDELTA_FIELD.parse_mikrotik_timedelta(str(value))
    except (ValueError, AttributeError):
        return None
    if delta is None:
        return None
    return int(delta.total_seconds())


def _reconcile_uptime_allowance(hotspot, active_resource, existing_entry, username, allowance_seconds, subscription_id):
    """
    Compute the limit-uptime (+ marker comment) kwargs for this write,
    applying the product's carry-over rule: unused connected time from a
    previous allowance rolls forward onto a repeat purchase under the same
    (reused - see Subscription.ensure_hotspot_credentials) username,
    rather than being lost or stacked on top of a fresh allowance.

    Returns a dict to merge into write_kwargs - may be empty, meaning
    "don't touch limit-uptime/comment on this call". Never raises for
    expected conditions; a RouterOS failure on reset-counters propagates
    like any other write in provision_hotspot_user (same unreachable-
    router failure path as today).

    Carry-over is 0 whenever it can't be established honestly: no
    previous limit-uptime on the entry (new account, or an account that
    was previously provisioned Unlimited), or a value that fails to parse.
    Never infer a "remaining" figure from an uptime counter with no prior
    allowance to compare it against.
    """
    if existing_entry is None:
        # Brand new account: nothing accumulated, nothing to carry, nothing
        # on the router yet to reset.
        kwargs = {}
        if allowance_seconds is not None:
            kwargs['limit_uptime'] = f"{allowance_seconds}s"
        if subscription_id is not None:
            kwargs['comment'] = f"sz-alloc:{subscription_id}"
        return kwargs

    marker = f"sz-alloc:{subscription_id}" if subscription_id is not None else None
    if marker is not None and existing_entry.get('comment') == marker:
        # This exact purchase's allowance was already applied to this
        # router entry (e.g. a concurrent activation retry) - recomputing
        # again here would carry-over the allowance we just added on top
        # of itself. No-op: password/profile/data-limit above still get
        # (re)written as normal, just not limit-uptime/comment.
        logger.info(
            "Hotspot user %s: allowance for subscription %s already applied on this router entry; "
            "skipping limit-uptime recompute.",
            username, subscription_id,
        )
        return {}

    online = active_resource.get(user=username)
    if online:
        # Resetting counters on an account with a live session would zero
        # out the time it's already spent this session, handing out free
        # connected time. Refuse rather than reset blind - the new
        # allowance (and any carry-over) gets applied on the next
        # reprovision while this account is offline, same as any other
        # write this function might defer.
        logger.warning(
            "Hotspot user %s is currently online (active on router); skipping limit-uptime carry-over "
            "recompute to avoid resetting counters mid-session. New allowance will be applied on the "
            "next reprovision while the account is offline.",
            username,
        )
        return {}

    old_limit_raw = existing_entry.get('limit-uptime')
    old_uptime_seconds = _parse_routeros_duration_seconds(existing_entry.get('uptime')) or 0
    old_limit_seconds = _parse_routeros_duration_seconds(old_limit_raw)

    if old_limit_seconds is None:
        # No previous allowance to compare against (new-to-this-feature
        # account, or previously provisioned Unlimited) - nothing to carry.
        carry_over_seconds = 0
    else:
        carry_over_seconds = max(0, old_limit_seconds - old_uptime_seconds)

    hotspot.call('reset-counters', {'numbers': existing_entry['id']})

    kwargs = {}
    if allowance_seconds is None:
        # Unlimited: no cap to carry into. Explicitly clear any previous
        # numeric cap rather than leaving a stale one in place - "" is
        # RouterOS's own way to unset an optional field (None here would
        # just mean "don't send this kwarg at all", see _set()/_add()).
        if old_limit_raw:
            kwargs['limit_uptime'] = ''
    else:
        kwargs['limit_uptime'] = f"{carry_over_seconds + allowance_seconds}s"
    if marker is not None:
        kwargs['comment'] = marker
    return kwargs


def _add(resource, **kwargs):
    """
    RouterOS API requires every argument value to be str/bytes - the
    routeros_api library's encoding layer calls .encode() unconditionally on
    anything that isn't already bytes, so a bare int (limit_bytes_total=0),
    or any other non-str value returned from a prior .get() call and reused
    here (RouterOS-typed fields can come back as int/timedelta/etc, not just
    str), crashes with "'<type>' object has no attribute 'encode'". This is
    exactly what broke every hotspot activation - confirmed in production.
    Stringify every argument here rather than trusting each call site to
    remember, and drop None entirely (RouterOS has no "set this to null").
    """
    resource.add(**{k: str(v) for k, v in kwargs.items() if v is not None})


def _set(resource, **kwargs):
    resource.set(**{k: str(v) for k, v in kwargs.items() if v is not None})


def provision_hotspot_user(router, mac_address, username, secret, plan=None, remaining_time=0, subscription_id=None):
    """
    Create/authorize a hotspot user on the physical router.

    subscription_id: optional idempotency marker for the limit-uptime
    carry-over dance below (see _reconcile_uptime_allowance) - pass the
    Subscription's own id so a concurrent/retried activation for the same
    purchase can't carry-over its own already-applied allowance on top of
    itself. Callers that don't have one (e.g. the admin-triggered
    activation endpoint) can omit it; the allowance is then recomputed on
    every call, same as before this parameter existed for them.

    Returns (success: bool, error: str|None). Never raises for expected
    failure modes (unmanaged router, unreachable router, unsupported type) -
    those are all reported back as (False, <message>) so callers can record
    them without needing their own try/except around every router type.
    """
    try:
        ensure_router_manages_hotspot_users(router, "activate hotspot user")
    except RouterNotManagedError as e:
        return False, str(e)

    try:
        if router.type == "mikrotik":
            from routeros_api import RouterOsApiPool
            from network_management.utils.mikrotik_connector import plan_to_profile_name, plan_uptime_limit_seconds
            api_pool = RouterOsApiPool(
                router.ip,
                username=router.username,
                password=router.password,
                port=router.port,
                plaintext_login=True
            )
            try:
                api = api_pool.get_api()
                hotspot = api.get_resource("/ip/hotspot/user")
                active_resource = api.get_resource("/ip/hotspot/active")

                data_limit = _plan_data_limit_bytes(plan)
                allowance_seconds = plan_uptime_limit_seconds(plan)
                profile_name = plan_to_profile_name(plan) if plan is not None else ""

                # Idempotent: a repeat purchase under the same username (see
                # Subscription.ensure_hotspot_credentials - username is
                # derived deterministically per client, password is fresh
                # per subscription) must update the existing account rather
                # than blindly add a second one - a plain .add() here
                # crashed a real activation with RouterOS's "already have
                # user with this name for this server". This doubles as the
                # renewal/top-up path: buying more time under the same
                # account just updates it in place.
                #
                # No mac-address restriction: the client's MAC isn't stable
                # across reconnects (WiFi MAC randomization - confirmed two
                # different MACs from one device in router logs), and
                # RouterOS's own passive MAC-auth never applied to these
                # named accounts anyway (mac-auth-mode=mac-as-username on
                # this hotspot server profile looks for a user literally
                # *named* the MAC, not one with a mac-address field set).
                # Auth is by username/password alone.
                existing = hotspot.get(name=username)
                existing_entry = existing[0] if existing else None

                uptime_kwargs = _reconcile_uptime_allowance(
                    hotspot, active_resource, existing_entry, username, allowance_seconds, subscription_id,
                )

                write_kwargs = dict(
                    password=secret, profile=profile_name, limit_bytes_total=data_limit, **uptime_kwargs
                )
                if existing_entry:
                    _set(hotspot, id=existing_entry.get('id'), **write_kwargs)
                else:
                    _add(hotspot, name=username, **write_kwargs)

                if remaining_time and remaining_time > 0:
                    active = api.get_resource("/ip/hotspot/active").get(mac_address=mac_address.lower())
                    if active:
                        _set(
                            api.get_resource("/ip/hotspot/active"),
                            id=active[0].get('id'),
                            idle_timeout=f"{max(1, remaining_time // 60)}m",
                        )
            finally:
                api_pool.disconnect()

            return True, None

        elif router.type == "ubiquiti":
            import requests

            auth_minutes = max(1, remaining_time // 60) if remaining_time and remaining_time > 0 else 1440

            def to_int_if_numeric(val):
                try:
                    return int(float(val))
                except Exception:
                    return 0

            data = {
                "cmd": "authorize-guest",
                "mac": mac_address.lower(),
                "minutes": auth_minutes,
                "up": to_int_if_numeric(getattr(plan, "upload_speed_value", 0)) if plan is not None else 0,
                "down": to_int_if_numeric(getattr(plan, "download_speed_value", 0)) if plan is not None else 0,
                "bytes": _plan_data_limit_bytes(plan)
            }

            controller_url = f"https://{router.ip}:{router.port}/api/s/default/cmd/stamgr"
            response = requests.post(
                controller_url,
                json=data,
                auth=(router.username, router.password),
                verify=False,
                timeout=10
            )

            if response.status_code == 200:
                return True, None
            return False, f"Ubiquiti API error: {response.status_code}"

        elif router.type == "cisco":
            return True, None

        else:
            return False, f"Unsupported router type: {router.type}"

    except Exception as e:
        logger.exception("Error provisioning hotspot user on router %s", getattr(router, 'id', 'unknown'))
        return False, str(e)


def provision_pppoe_user(router, username, secret, plan=None, remote_address=None, remaining_time=0):
    """
    Create a PPPoE secret on the physical router. Same contract as
    provision_hotspot_user: returns (success, error), never raises for
    expected failure modes.
    """
    try:
        ensure_router_manages_hotspot_users(router, "activate PPPoE user")
    except RouterNotManagedError as e:
        return False, str(e)

    try:
        if router.type == "mikrotik":
            from routeros_api import RouterOsApiPool
            from network_management.utils.mikrotik_connector import plan_to_profile_name
            api_pool = RouterOsApiPool(
                router.ip,
                username=router.username,
                password=router.password,
                port=router.port,
                plaintext_login=True
            )
            try:
                api = api_pool.get_api()
                pppoe_secret = api.get_resource("/ppp/secret")

                # Same plan_to_profile_name() as provision_hotspot_user() and
                # push_plan_profile() - the sanitized name is the only one
                # that's guaranteed to match a profile actually pushed to
                # the router; raw plan.name can contain characters RouterOS
                # rejects/mangles in a profile name.
                profile_name = plan_to_profile_name(plan) if plan is not None else "default"

                _add(
                    pppoe_secret,
                    name=username,
                    password=secret,
                    service="pppoe",
                    profile=profile_name,
                    remote_address=remote_address or "dynamic",
                )

                if remaining_time and remaining_time > 0:
                    _set(
                        api.get_resource("/ppp/profile"),
                        name=profile_name,
                        session_timeout=f"{max(1, remaining_time // 60)}m",
                    )
            finally:
                api_pool.disconnect()

            return True, None

        elif router.type == "ubiquiti":
            return True, "PPPoE configuration not supported on Ubiquiti routers"

        elif router.type == "cisco":
            return True, None

        else:
            return False, f"Unsupported router type for PPPoE: {router.type}"

    except Exception as e:
        logger.exception("Error provisioning PPPoE user on router %s", getattr(router, 'id', 'unknown'))
        return False, str(e)
