"""Rate limits (P14.1). State lives in the database, so every web process sees the same counts.

* Sign-in: at most ``SIGNIN_FAILURES_PER_IP`` failed attempts from one address in
  ``SIGNIN_WINDOW_MINUTES`` (counted from the audit log by the ``signin_failures`` database
  function), on top of the per-account lock (P1.4).
* Exports and imports: at most ``JOBS_PENDING_PER_USER`` waiting at once and
  ``JOBS_PER_USER_PER_HOUR`` per hour.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

SIGNIN_FAILURES_PER_IP = 20
SIGNIN_WINDOW_MINUTES = 15
JOBS_PENDING_PER_USER = 3
JOBS_PER_USER_PER_HOUR = 30


class RateLimited(Exception):  # noqa: N818
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def check_signin(ip: str | None) -> None:
    if not ip:
        return
    from django.db import connection

    since = timezone.now() - timedelta(minutes=SIGNIN_WINDOW_MINUTES)
    limit = getattr(settings, "SIGNIN_FAILURES_PER_IP", SIGNIN_FAILURES_PER_IP)
    with connection.cursor() as cur:  # SECURITY DEFINER: counts across agencies, returns a number
        cur.execute("SELECT signin_failures(%s::inet, %s)", [ip, since])
        failures = cur.fetchone()[0]
    if failures >= limit:
        raise RateLimited(
            "Too many failed sign-ins from this network address. "
            f"Wait {SIGNIN_WINDOW_MINUTES} minutes and try again."
        )


def check_jobs(user, kinds) -> None:
    from apps.jobs.models import Job

    mine = Job.objects.filter(requested_by=user, kind__in=list(kinds))
    if mine.filter(status__in=[Job.Status.QUEUED, Job.Status.RUNNING]).count() >= JOBS_PENDING_PER_USER:
        raise RateLimited(
            f"You already have {JOBS_PENDING_PER_USER} files being prepared. Wait until one is ready."
        )
    if mine.filter(created_at__gte=timezone.now() - timedelta(hours=1)).count() >= JOBS_PER_USER_PER_HOUR:
        raise RateLimited(f"At most {JOBS_PER_USER_PER_HOUR} exports or imports an hour. Try again later.")


def too_many(err: RateLimited):
    from rest_framework.response import Response

    return Response({"detail": err.message, "code": "rate_limited"}, status=429)
