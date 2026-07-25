from django.views.generic import TemplateView

from internet_plans.models.plan_models import InternetPlan


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

        context["mac"] = self.request.GET.get("mac", "")
        context["ip"] = self.request.GET.get("ip", "")
        context["link_login_only"] = self.request.GET.get("link-login-only", "")
        context["link_orig"] = self.request.GET.get("link-orig", "")
        context["dst"] = self.request.GET.get("dst", "")

        # Mirrors the hotspot filter used by PublicInternetPlanListView
        # (internet_plans/api/views/plan_views.py) for client_type=hotspot.
        plans = (
            InternetPlan.objects.filter(active=True)
            .filter(access_methods__hotspot__enabled=True)
            .order_by("price", "name")
        )

        context["plans"] = plans
        context["plans_empty"] = not plans.exists()

        return context
