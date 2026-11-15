from django.urls import path

from apps.tenancy import platform_api as api

urlpatterns = [
    path("auth/login", api.PlatformLoginView.as_view(), name="platform-login"),
    path("auth/logout", api.PlatformLogoutView.as_view(), name="platform-logout"),
    path("me", api.PlatformMeView.as_view(), name="platform-me"),
    path("agencies", api.AgencyListView.as_view(), name="platform-agencies"),
    path("agencies/<uuid:agency_id>", api.AgencyDetailView.as_view(), name="platform-agency"),
    path(
        "agencies/<uuid:agency_id>/admins", api.AgencyAdminCreateView.as_view(), name="platform-agency-admins"
    ),
    path(
        "agencies/<uuid:agency_id>/support", api.AgencySupportView.as_view(), name="platform-agency-support"
    ),
]
