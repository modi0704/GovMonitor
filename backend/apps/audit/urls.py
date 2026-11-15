from django.urls import path

from apps.audit import api

urlpatterns = [
    path("audit-log", api.AuditLogListView.as_view(), name="audit-log"),
    path("audit-log/export.csv", api.AuditLogCsvView.as_view(), name="audit-log-csv"),
    path("audit-log/<int:row_id>", api.AuditLogDetailView.as_view(), name="audit-log-row"),
]
