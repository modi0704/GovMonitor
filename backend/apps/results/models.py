"""Frozen results (MASTERPLAN 6.4 period_result): written only when a period is locked (P7.3)."""

from django.db import models

from apps.planning.models import MONEY, RATIO
from apps.tenancy.models import TenantModel


class PeriodResult(TenantModel):
    class View(models.TextChoices):
        OWNER = "owner"
        IMPLEMENTING = "implementing"

    period = models.ForeignKey("planning.ReportingPeriod", on_delete=models.PROTECT, related_name="results")
    office = models.ForeignKey("structure.Office", on_delete=models.PROTECT, related_name="+")
    view = models.CharField(max_length=14, choices=View.choices)
    plan_version = models.PositiveIntegerField(null=True, blank=True)  # own plan's version, if any
    periodic_plan = models.DecimalField(**{**RATIO, "max_digits": 20})
    periodic_actual = models.DecimalField(**{**RATIO, "max_digits": 20})
    cum_plan = models.DecimalField(**{**RATIO, "max_digits": 20})
    cum_actual = models.DecimalField(**{**RATIO, "max_digits": 20})
    variance = models.DecimalField(**{**RATIO, "max_digits": 20})
    status_label = models.CharField(max_length=30)
    funds_total = models.DecimalField(**MONEY)
    funds_used_est = models.DecimalField(**MONEY)
    funds_used_actual = models.DecimalField(null=True, blank=True, **MONEY)
    indicator_score = models.DecimalField(null=True, blank=True, **{**RATIO, "max_digits": 20})
    rank_sibling = models.PositiveIntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict)
    profile_snapshot = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "period_result"
        constraints = [
            models.UniqueConstraint(fields=["period", "office", "view"], name="period_result_unique"),
        ]
