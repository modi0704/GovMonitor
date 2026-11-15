"""Monthly reporting: submissions, actuals, supporting files (MASTERPLAN 6.4, Phase 6)."""

from decimal import Decimal

from django.db import models

from apps.planning.models import MONEY, QTY
from apps.tenancy.models import TenantModel


class OfficeSubmission(TenantModel):
    """One office's monthly report for one period."""

    class Status(models.TextChoices):
        DRAFT = "draft"
        SUBMITTED = "submitted"
        RETURNED = "returned"
        LOCKED = "locked"

    office = models.ForeignKey("structure.Office", on_delete=models.PROTECT, related_name="submissions")
    period = models.ForeignKey("planning.ReportingPeriod", on_delete=models.PROTECT, related_name="submissions")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    submitted_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    returned_at = models.DateTimeField(null=True, blank=True)
    return_note = models.TextField(blank=True)

    class Meta:
        db_table = "office_submission"
        constraints = [models.UniqueConstraint(fields=["office", "period"], name="office_submission_unique")]

    @property
    def editable(self) -> bool:
        return self.status in (self.Status.DRAFT, self.Status.RETURNED)


class ActivityActual(TenantModel):
    """Accomplishment of one activity (by lineage, so plan revisions keep it) in one period."""

    activity_lineage_id = models.UUIDField()
    period = models.ForeignKey("planning.ReportingPeriod", on_delete=models.PROTECT, related_name="+")
    # The office that owns the plan line (D30): scope, audit filtering and submission status.
    office = models.ForeignKey("structure.Office", on_delete=models.PROTECT, related_name="+")
    actual_qty = models.DecimalField(default=Decimal("0"), **QTY)
    actual_amount = models.DecimalField(null=True, blank=True, **MONEY)
    remarks = models.TextField(blank=True)
    delay_reason = models.TextField(blank=True)
    entered_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    audit_exclude = frozenset({"updated_at", "entered_by_id"})

    class Meta:
        db_table = "activity_actual"
        constraints = [
            models.UniqueConstraint(fields=["activity_lineage_id", "period"], name="activity_actual_unique")
        ]
        indexes = [models.Index(fields=["agency", "office", "period"], name="activity_actual_office")]


class IndicatorActual(TenantModel):
    indicator_lineage_id = models.UUIDField()
    period = models.ForeignKey("planning.ReportingPeriod", on_delete=models.PROTECT, related_name="+")
    office = models.ForeignKey("structure.Office", on_delete=models.PROTECT, related_name="+")
    actual_value = models.DecimalField(null=True, blank=True, **QTY)
    remarks = models.TextField(blank=True)
    entered_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    audit_exclude = frozenset({"updated_at", "entered_by_id"})

    class Meta:
        db_table = "indicator_actual"
        constraints = [
            models.UniqueConstraint(fields=["indicator_lineage_id", "period"], name="indicator_actual_unique")
        ]
        indexes = [models.Index(fields=["agency", "office", "period"], name="indicator_actual_office")]


class Attachment(TenantModel):
    """A supporting file (MOV). Soft-deleted: the stored file is kept."""

    class TargetType(models.TextChoices):
        ACTIVITY_ACTUAL = "activity_actual"
        INDICATOR_ACTUAL = "indicator_actual"

    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.UUIDField()
    office = models.ForeignKey("structure.Office", on_delete=models.PROTECT, related_name="+")  # D30
    period = models.ForeignKey("planning.ReportingPeriod", on_delete=models.PROTECT, related_name="+")  # P7.5
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size_bytes = models.BigIntegerField()
    sha256 = models.CharField(max_length=64)
    storage_key = models.CharField(max_length=500)
    description = models.CharField(max_length=500, blank=True)
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "attachment"
        indexes = [models.Index(fields=["agency", "target_type", "target_id"], name="attachment_target")]
