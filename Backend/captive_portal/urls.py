from django.urls import path

from .views import PortalBuyView

urlpatterns = [
    path("connect/", PortalBuyView.as_view(), name="portal-buy"),
]
