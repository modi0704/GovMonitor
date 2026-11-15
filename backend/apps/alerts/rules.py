"""The agency's alert rule (P11.1)."""

from decimal import Decimal, InvalidOperation

from django.conf import settings

from apps.alerts.models import AlertRule

MAX_REMINDERS = 5
MAX_DAYS = 31


class RuleError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def current() -> AlertRule:
    """The agency's rule, or the defaults (unsaved) when it has never been changed."""
    return AlertRule.objects.first() or AlertRule()


def update(changes: dict) -> AlertRule:
    rule = AlertRule.objects.first() or AlertRule()
    if "remind_days_before" in changes:
        raw = changes["remind_days_before"]
        if isinstance(raw, str):
            raw = [p for p in raw.replace(";", ",").split(",") if p.strip()]
        try:
            days = sorted({int(str(d).strip()) for d in raw or []}, reverse=True)
        except (TypeError, ValueError) as exc:
            raise RuleError("remind_days_before", "Use whole numbers of days, e.g. 5, 1.") from exc
        if any(d < 0 or d > MAX_DAYS for d in days) or len(days) > MAX_REMINDERS:
            raise RuleError(
                "remind_days_before", f"At most {MAX_REMINDERS} reminders, each 0 to {MAX_DAYS} days before."
            )
        rule.remind_days_before = days
    if "delay_threshold" in changes:
        try:
            threshold = Decimal(str(changes["delay_threshold"]))
        except (InvalidOperation, ValueError) as exc:
            raise RuleError("delay_threshold", "Enter a number.") from exc
        if not (Decimal(0) <= threshold <= Decimal(1)):
            raise RuleError("delay_threshold", "Use a share between 0 and 1 (e.g. 0.05 for 5 points).")
        rule.delay_threshold = threshold
    if "email_enabled" in changes:
        rule.email_enabled = bool(changes["email_enabled"])
    rule.save()
    return rule


def payload(rule: AlertRule) -> dict:
    from apps.planning.numbers import plain

    return {
        "remind_days_before": list(rule.remind_days_before),
        "delay_threshold": plain(rule.delay_threshold),
        "email_enabled": rule.email_enabled,
        "email_available": bool(settings.EMAIL_ENABLED),
    }
