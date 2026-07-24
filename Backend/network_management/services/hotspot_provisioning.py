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

from network_management.utils.router_guard import ensure_router_manages_hotspot_users, RouterNotManagedError

logger = logging.getLogger(__name__)


def provision_hotspot_user(router, mac_address, username, secret, plan=None, remaining_time=0):
    """
    Create/authorize a hotspot user on the physical router.

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

                data_limit = 0
                if plan is not None and getattr(plan, "data_limit_value", None) and str(plan.data_limit_value).lower() != 'unlimited':
                    try:
                        multiplier = 1024 ** 3 if plan.data_limit_unit == "GB" else 1024 ** 4
                        data_limit = int(float(plan.data_limit_value) * multiplier)
                    except Exception:
                        data_limit = 0

                hotspot.add(
                    name=username,
                    password=secret,
                    profile=getattr(plan, "name", "") if plan is not None else "",
                    mac_address=mac_address.lower(),
                    limit_bytes_total=data_limit
                )

                if remaining_time and remaining_time > 0:
                    active = api.get_resource("/ip/hotspot/active").get(mac_address=mac_address.lower())
                    if active:
                        api.get_resource("/ip/hotspot/active").set(
                            id=active[0].get('id'),
                            idle_timeout=f"{max(1, remaining_time // 60)}m"
                        )
            finally:
                api_pool.disconnect()

            return True, None

        elif router.type == "ubiquiti":
            import requests
            controller_url = f"https://{router.ip}:{router.port}/api/s/default/cmd/stamgr"
            auth_minutes = max(1, remaining_time // 60) if remaining_time and remaining_time > 0 else 1440

            def to_int_if_numeric(val):
                try:
                    return int(float(val))
                except Exception:
                    return 0

            bytes_limit = 0
            if plan is not None and getattr(plan, "data_limit_value", None) and str(plan.data_limit_value).lower() != 'unlimited':
                try:
                    mul = 1024 ** 3 if plan.data_limit_unit == "GB" else 1024 ** 4
                    bytes_limit = int(float(plan.data_limit_value) * mul)
                except Exception:
                    bytes_limit = 0

            data = {
                "cmd": "authorize-guest",
                "mac": mac_address.lower(),
                "minutes": auth_minutes,
                "up": to_int_if_numeric(getattr(plan, "upload_speed_value", 0)) if plan is not None else 0,
                "down": to_int_if_numeric(getattr(plan, "download_speed_value", 0)) if plan is not None else 0,
                "bytes": bytes_limit
            }

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

                pppoe_secret.add(
                    name=username,
                    password=secret,
                    service="pppoe",
                    profile=getattr(plan, "name", "default") if plan is not None else "default",
                    remote_address=remote_address or "dynamic"
                )

                if remaining_time and remaining_time > 0:
                    profile_resource = api.get_resource("/ppp/profile")
                    profile_resource.set(
                        name=getattr(plan, "name", "default") if plan is not None else "default",
                        session_timeout=f"{max(1, remaining_time // 60)}m"
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
