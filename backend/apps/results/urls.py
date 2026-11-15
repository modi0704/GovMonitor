from django.urls import path

from apps.results import api, dashboard_api

urlpatterns = [
    path("results/preview", api.PreviewView.as_view(), name="results-preview"),
    path("dashboard", dashboard_api.DashboardView.as_view(), name="dashboard"),
    path(
        "dashboard/activities", dashboard_api.DashboardActivitiesView.as_view(), name="dashboard-activities"
    ),
    path("dashboard/activity", dashboard_api.ActivityHistoryView.as_view(), name="dashboard-activity"),
    path("periods/<uuid:period_id>/lock", api.PeriodLockView.as_view(), name="period-lock"),
    path("periods/<uuid:period_id>/unlock", api.PeriodUnlockView.as_view(), name="period-unlock"),
]
