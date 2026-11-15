from django.urls import path

from apps.reporting import attachments_api

urlpatterns = [
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
