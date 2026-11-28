"""The daily alert scan as a worker job (P11.2, MASTERPLAN 6.7)."""

import datetime

from django.utils import timezone

from apps.jobs.models import Job
from apps.jobs.worker import enqueue, handler, scheduler

SCAN_HOUR = 6  # local time: the scan is queued at the first worker pass after 06:00


@handler(Job.Kind.ALERT_SCAN)
def alert_scan(job: Job) -> dict:
    from apps.alerts import email, services

    counts = services.scan()
    counts["emails"] = email.send_digests()
    return counts


@scheduler
def schedule_alert_scan(now=None) -> int:
    """Queue one alert_scan per agency per local day, after SCAN_HOUR (idempotent)."""
    from django.conf import settings

    if not settings.ALERTS_ENABLED:
        return 0  # D49: the daily alert scan does not run
    from apps.alerts.services import _tz
    from apps.tenancy import context

    now = now or timezone.now()
    tz = _tz(context.require_agency_id())
    local = now.astimezone(tz)
    if local.hour < SCAN_HOUR:
        return 0
    start_of_day = datetime.datetime.combine(local.date(), datetime.time.min, tzinfo=tz)
    if Job.objects.filter(kind=Job.Kind.ALERT_SCAN, created_at__gte=start_of_day).exists():
        return 0
    enqueue(Job.Kind.ALERT_SCAN, {"local_date": local.date().isoformat()})
    return 1
