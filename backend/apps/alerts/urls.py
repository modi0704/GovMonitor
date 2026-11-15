from django.urls import path

from apps.alerts import api

urlpatterns = [
    path("alert-rules", api.AlertRuleView.as_view(), name="alert-rules"),
]
