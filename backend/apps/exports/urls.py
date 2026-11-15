from django.urls import path

from apps.exports import api, import_api

urlpatterns = [
    path("exports/xlsx", api.XlsxExportView.as_view(), name="export-xlsx"),
    path("imports/plan-template", import_api.PlanTemplateView.as_view(), name="import-plan-template"),
    path("imports/plan", import_api.PlanImportView.as_view(), name="import-plan"),
]
