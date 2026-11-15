"""Export templates (MASTERPLAN 6.4 export_template, P10.2)."""

import uuid

from django.db import models

from apps.audit.services import AuditedModel


class ExportTemplate(AuditedModel):
    """Titles, colours and logo use for exports. ``agency`` null = the system default, readable by
    every agency (``global_read`` policy) and writable by none."""

    class Kind(models.TextChoices):
        XLSX = "xlsx"
        PPTX = "pptx"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "tenancy.Agency", on_delete=models.PROTECT, related_name="+", null=True, blank=True, editable=False
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    name = models.CharField(max_length=120)
    settings = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "export_template"
        constraints = [
            models.UniqueConstraint(
                fields=["agency", "kind"],
                condition=models.Q(is_default=True, agency__isnull=False),
                name="export_template_one_default_per_agency",
            ),
            models.UniqueConstraint(
                fields=["kind"],
                condition=models.Q(is_default=True, agency__isnull=True),
                name="export_template_one_system_default",
            ),
        ]
        indexes = [models.Index(fields=["agency", "kind"], name="export_template_agency_kind")]
