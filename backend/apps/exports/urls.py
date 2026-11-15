from django.urls import path

from apps.exports import api

urlpatterns = [
    path("exports/xlsx", api.XlsxExportView.as_view(), name="export-xlsx"),
]
