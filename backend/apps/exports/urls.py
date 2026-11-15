from django.urls import path

from apps.exports import api, import_api, template_api

urlpatterns = [
    path("exports/xlsx", api.XlsxExportView.as_view(), name="export-xlsx"),
    path("exports/pptx", api.PptxExportView.as_view(), name="export-pptx"),
    path("imports/plan-template", import_api.PlanTemplateView.as_view(), name="import-plan-template"),
    path("imports/plan", import_api.PlanImportView.as_view(), name="import-plan"),
    path("export-templates/<str:kind>", template_api.ExportTemplateView.as_view(), name="export-template"),
    path(
        "export-templates/<str:kind>/logo",
        template_api.ExportTemplateLogoView.as_view(),
        name="export-template-logo",
    ),
]
