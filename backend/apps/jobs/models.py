"""Background jobs (MASTERPLAN 6.5, 6.7): exports, imports, alert scans, automatic locking."""

from django.db import models

from apps.tenancy.models import TenantModel


class Job(TenantModel):
    class Kind(models.TextChoices):
        EXPORT_XLSX = "export_xlsx"
        EXPORT_PPTX = "export_pptx"
        IMPORT_PLAN = "import_plan"
        ALERT_SCAN = "alert_scan"
        LOCK_PERIOD = "lock_period"

    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        DONE = "done"
        FAILED = "failed"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    result_key = models.CharField(max_length=500, blank=True)
    result = models.JSONField(default=dict, blank=True)  # small summary for the UI (D32)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    audit_exclude = frozenset({"started_at", "attempts"})

    class Meta:
        db_table = "job"
        indexes = [
            models.Index(fields=["status", "created_at"], name="job_status_created"),
            models.Index(fields=["agency", "kind", "status"], name="job_agency_kind_status"),
        ]
