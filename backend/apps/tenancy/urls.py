from django.urls import path

from apps.tenancy import api

urlpatterns = [
    path("agency", api.AgencyView.as_view(), name="agency"),
    path("support-grants", api.SupportGrantListView.as_view(), name="support-grants"),
    path("support-grants/<uuid:grant_id>", api.SupportGrantRevokeView.as_view(), name="support-grant"),
]
