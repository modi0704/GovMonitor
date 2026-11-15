from django.urls import path

from apps.planning import api

urlpatterns = [
    path("fiscal-years", api.FiscalYearListView.as_view(), name="fiscal-years"),
    path("fiscal-years/<uuid:fy_id>", api.FiscalYearDetailView.as_view(), name="fiscal-year"),
    path("scoring-presets", api.PresetListView.as_view(), name="scoring-presets"),
    path("scoring-profiles/<uuid:profile_id>", api.ScoringProfileView.as_view(), name="scoring-profile"),
]
