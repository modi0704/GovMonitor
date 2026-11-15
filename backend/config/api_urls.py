from django.urls import include, path

from config.health import health

urlpatterns = [
    path("health", health, name="health"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.tenancy.urls")),
    path("", include("apps.structure.urls")),
    path("", include("apps.audit.urls")),
    path("", include("apps.planning.urls")),
    path("", include("apps.results.urls")),
    path("", include("apps.reporting.urls")),
]
