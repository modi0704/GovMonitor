from django.urls import path

from apps.jobs import api

urlpatterns = [
    path("jobs", api.JobListView.as_view(), name="jobs"),
    path("jobs/<uuid:job_id>", api.JobDetailView.as_view(), name="job"),
    path("jobs/<uuid:job_id>/download", api.JobDownloadView.as_view(), name="job-download"),
]
