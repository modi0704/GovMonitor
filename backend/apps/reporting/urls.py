from django.urls import path

from apps.reporting import api, attachments_api, progress_api

urlpatterns = [
    path("reports", api.ReportView.as_view(), name="reports"),
    path("reports/save", api.ReportSaveView.as_view(), name="reports-save"),
    path("reports/preview", api.ReportPreviewView.as_view(), name="reports-preview"),
    path("reports/submit", api.ReportSubmitView.as_view(), name="reports-submit"),
    path("submission-board", api.SubmissionBoardView.as_view(), name="submission-board"),
    path("reports/return", api.ReportReturnView.as_view(), name="reports-return"),
    path("progress", progress_api.ProgressView.as_view(), name="progress"),
    path("attachments", attachments_api.AttachmentListView.as_view(), name="attachments"),
    path(
        "attachments/<uuid:attachment_id>", attachments_api.AttachmentDetailView.as_view(), name="attachment"
    ),
    path(
        "attachments/<uuid:attachment_id>/download",
        attachments_api.AttachmentDownloadView.as_view(),
        name="attachment-download",
    ),
]
