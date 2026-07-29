from urllib.parse import urlencode

from django.views.generic import TemplateView

from internet_plans.models.plan_models import InternetPlan

# Router params MikroTik's walled-garden redirect appends to the /connect/
# link; (context_key, querystring_key) so both are handy from one table.
ROUTER_PARAMS = (
    ("mac", "mac"),
    ("ip", "ip"),
    ("link_login_only", "link-login-only"),
    ("link_orig", "link-orig"),
    ("dst", "dst"),
)

# Elevated priority levels (see InternetPlan.PRIORITY_LEVELS) worth a tier
# badge on their own, even outside the Business/Enterprise categories.
BADGE_PRIORITY_LEVELS = {5, 6, 7, 8}
BADGE_CATEGORIES = {"Business", "Enterprise"}


class PortalBuyView(TemplateView):
    """
    Captive portal landing/buy page. MikroTik's walled-garden redirect lands
    the client here with router params (mac, ip, link-login-only, link-orig,
    dst) in the query string; the page echoes them back in hidden fields so
    they survive the eventual POST to the router's login URL.
    """

    template_name = "captive_portal/buy.html"
    http_method_names = ["get"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        router_qs_params = {}
        for ctx_key, qs_key in ROUTER_PARAMS:
            value = self.request.GET.get(qs_key, "")
            context[ctx_key] = value
            if value:
                router_qs_params[qs_key] = value

        def build_url(category=None, plan=None):
            params = dict(router_qs_params)
            if category:
                params["category"] = category
            if plan:
                params["plan"] = str(plan)
            qs = urlencode(params)
            return "/connect/" + (f"?{qs}" if qs else "")

        # Mirrors the hotspot filter used by PublicInternetPlanListView
        # (internet_plans/api/views/plan_views.py) for client_type=hotspot.
        base_queryset = InternetPlan.objects.filter(
            active=True, access_methods__hotspot__enabled=True
        )

        available_categories = set(
            base_queryset.values_list("category", flat=True).distinct()
        )
        valid_categories = {value for value, _label in InternetPlan.CATEGORIES}

        requested_category = self.request.GET.get("category", "")
        active_category = (
            requested_category if requested_category in valid_categories else None
        )

        queryset = base_queryset
        if active_category:
            queryset = queryset.filter(category=active_category)
        plans = list(queryset.order_by("price", "name"))

        requested_plan = self.request.GET.get("plan", "")
        selected_plan = None

        for plan in plans:
            plan.badge_label = _tier_badge_label(plan)
            plan.download_speed = _download_speed(plan)
            plan.validity_label = _validity_label(plan)
            plan.data_line = _data_line(plan)
            plan.price_display = _format_price(plan.price)
            plan.selected = requested_plan and str(plan.id) == requested_plan
            plan.choose_url = build_url(category=active_category, plan=plan.id)
            if plan.selected:
                selected_plan = plan

        category_tabs = [
            {
                "label": label,
                "value": value,
                "active": active_category == value,
                "url": build_url(category=value),
            }
            for value, label in InternetPlan.CATEGORIES
            if value in available_categories
        ]

        context["plans"] = plans
        context["plans_empty"] = not plans
        context["category_tabs"] = category_tabs
        context["active_category"] = active_category
        context["all_plans_url"] = build_url()
        context["selected_plan"] = selected_plan

        return context


def _tier_badge_label(plan):
    """Only badges what the plan data actually supports (no invented flags)."""
    if plan.category in BADGE_CATEGORIES:
        return plan.category
    if plan.priority_level in BADGE_PRIORITY_LEVELS:
        return plan.get_priority_level_display()
    return ""


def _download_speed(plan):
    speed = (plan.access_methods or {}).get("hotspot", {}).get("download_speed", {})
    value = speed.get("value") if isinstance(speed, dict) else ""
    unit = speed.get("unit") if isinstance(speed, dict) else ""
    if not value:
        return ""
    return f"{value} {unit}".strip()


def _validity_label(plan):
    validity = (plan.access_methods or {}).get("hotspot", {}).get("validity_period", {})
    value = validity.get("value") if isinstance(validity, dict) else ""
    unit = validity.get("unit") if isinstance(validity, dict) else ""
    if not value:
        return ""
    return f"{value} {unit}".strip()


def _data_line(plan):
    if plan.fup_policy:
        return f"Unlimited · FUP applies after {plan.fup_threshold}% usage"
    return "Unlimited"


def _format_price(price):
    """'KSh 20' for whole shillings, 'KSh 20.50' when genuinely fractional."""
    if price == price.to_integral_value():
        return f"{int(price)}"
    return f"{price:.2f}"
