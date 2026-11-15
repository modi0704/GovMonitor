"""Alerts (MASTERPLAN 6.4 alert_rule / notification, F12, D16)."""

from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.tenancy.models import TenantModel


def default_remind_days():
    return [5, 1]


class AlertRule(TenantModel):
    """One per agency: when reminders go out and what counts as a delay worth an alert."""

    remind_days_before = ArrayField(models.PositiveSmallIntegerField(), default=default_remind_days)
    delay_threshold = models.DecimalField(max_digits=14, decimal_places=10, default=Decimal("0.05"))
    email_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "alert_rule"
        constraints = [models.UniqueConstraint(fields=["agency"], name="alert_rule_one_per_agency")]


class Notification(TenantModel):
    """An in-app message for one user. Created in bulk by the scan and by events (never audited:
    it is derived from audited changes); ``dedupe_key`` stops the same alert being sent twice."""

    class Type(models.TextChoices):
        CUTOFF_REMINDER = "cutoff_reminder"
        CUTOFF_PASSED = "cutoff_passed"
        MISSING_ACTUALS = "missing_actuals"
        DELAYED = "delayed"
        SUBMISSION_RETURNED = "submission_returned"
        PERIOD_LOCKED = "period_locked"
        PERIOD_UNLOCKED = "period_unlocked"
        PLAN_SUBMITTED = "plan_submitted"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=24, choices=Type.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=300)

    class Meta:
        db_table = "notification"
        constraints = [
            models.UniqueConstraint(fields=["agency", "dedupe_key"], name="notification_agency_dedupe")
        ]
        indexes = [
            models.Index(fields=["agency", "user", "read_at"], name="notification_user_unread"),
            models.Index(fields=["agency", "user", "created_at"], name="notification_user_created"),
        ]
