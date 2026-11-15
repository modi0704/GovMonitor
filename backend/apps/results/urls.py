from django.urls import path

from apps.results import api

urlpatterns = [
    path("results/preview", api.PreviewView.as_view(), name="results-preview"),
    path("periods/<uuid:period_id>/lock", api.PeriodLockView.as_view(), name="period-lock"),
    path("periods/<uuid:period_id>/unlock", api.PeriodUnlockView.as_view(), name="period-unlock"),
]
