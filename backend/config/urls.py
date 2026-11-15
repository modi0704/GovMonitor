from django.urls import include, path, re_path

from config.views import spa_index

urlpatterns = [
    path("api/v1/", include("config.api_urls")),
    path("platform/api/", include("apps.tenancy.platform_urls")),
    # Everything else is the single-page app (client-side routing).
    re_path(r"^(?!api/|static/|platform/api/).*$", spa_index, name="spa"),
]
