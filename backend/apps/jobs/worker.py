"""Job queue worker (MASTERPLAN 6.7, P7.7).

Loop: claim the oldest queued job (``claim_next_job()``: FOR UPDATE SKIP LOCKED), run its handler
inside the job's agency context, mark it done or failed; a failed job is retried up to 3 attempts.
Jobs left ``running`` for more than 30 minutes are re-queued when a worker starts. The same loop
runs the scheduler pass, whose state lives entirely in the database (it is idempotent: it looks at
periods and existing jobs, never at memory).
"""

import logging
import traceback
from collections.abc import Callable

from django.db import connection, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.jobs.models import Job
from apps.tenancy import context

log = logging.getLogger("worker")

MAX_ATTEMPTS = 3
STALE_MINUTES = 30
HANDLERS: dict[str, Callable[[Job], dict | None]] = {}


class JobRejected(Exception):  # noqa: N818 — a refusal, not a crash
    """Raised by a handler when the job cannot succeed as asked (e.g. an import with errors): the
    handler's database work is rolled back and the job fails at once, without retries, keeping
    ``result`` (e.g. a row-by-row error list) for the UI."""

    def __init__(self, message: str, result: dict | None = None):
        super().__init__(message)
        self.message = message
        self.result = result or {}


def handler(kind: str):
    def register(fn):
        HANDLERS[kind] = fn
        return fn

    return register


def enqueue(kind: str, params: dict | None = None, user=None) -> Job:
    """Queue a job for the current agency (callers run inside an agency context)."""
    return Job.objects.create(kind=kind, params=params or {}, requested_by=user)


def requeue_stale() -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT requeue_stale_jobs(%s)", [STALE_MINUTES])
        return cur.fetchone()[0]


def claim() -> tuple | None:
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SELECT job_id, job_agency_id FROM claim_next_job()")
        return cur.fetchone()


def run_job(job_id, agency_id) -> str:
    """Run one claimed job in its agency's context. Returns the final status."""
    with context.agency_context(agency_id):
        job = Job.objects.get(pk=job_id)
        fn = HANDLERS.get(job.kind)
        try:
            if fn is None:
                raise RuntimeError(f"no handler for job kind {job.kind!r}")
            with transaction.atomic(), audit.acting_as("system", label=f"worker:{job.kind}"):
                result = fn(job) or {}
        except JobRejected as exc:
            job.refresh_from_db()
            job.status = Job.Status.FAILED
            job.error = exc.message[:8000]
            job.result = exc.result
            job.result_key = ""
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error", "result", "result_key", "finished_at"])
            return job.status
        except Exception as exc:  # noqa: BLE001 — every failure is recorded on the job
            job.refresh_from_db()
            job.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=5)}"[:8000]
            job.status = Job.Status.QUEUED if job.attempts < MAX_ATTEMPTS else Job.Status.FAILED
            if job.status == Job.Status.FAILED:
                job.finished_at = timezone.now()
            job.save(update_fields=["error", "status", "finished_at"])
            log.warning("job %s (%s) failed, attempt %s: %s", job.pk, job.kind, job.attempts, exc)
            return job.status
        job.refresh_from_db()
        job.status = Job.Status.DONE
        job.result = result
        job.error = ""
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "result", "error", "finished_at", "result_key"])
        return job.status


def agencies() -> list:
    with connection.cursor() as cur:
        cur.execute("SELECT active_agency_ids()")
        return [row[0] for row in cur.fetchall()]


SCHEDULERS: list[Callable[[], int]] = []


def scheduler(fn):
    """Register a per-agency scheduler: runs inside an agency context, returns jobs queued."""
    SCHEDULERS.append(fn)
    return fn


def schedule_pass() -> int:
    queued = 0
    for agency_id in agencies():
        with context.agency_context(agency_id):
            for fn in SCHEDULERS:
                queued += fn() or 0
    return queued


def run_pending(limit: int = 100) -> int:
    """Claim and run queued jobs until none is left (or ``limit``). Returns the number run."""
    done = 0
    while done < limit:
        claimed = claim()
        if not claimed:
            break
        run_job(*claimed)
        done += 1
    return done


# ---- Built-in jobs ------------------------------------------------------------------------------


@handler(Job.Kind.LOCK_PERIOD)
def lock_period_job(job: Job) -> dict:
    from apps.planning.models import ReportingPeriod
    from apps.results.locking import LockError, lock_period

    period = ReportingPeriod.objects.select_related("fiscal_year__profile").get(pk=job.params["period_id"])
    if period.status == ReportingPeriod.Status.LOCKED:
        return {"skipped": "already locked"}
    try:
        count = lock_period(period, job.requested_by)
    except LockError as err:
        if err.code == "earlier_open":
            return {"skipped": err.message}
        raise
    return {"locked": str(period.pk), "results": count}


@scheduler
def schedule_auto_lock() -> int:
    """When the profile says ``auto_lock``, queue a lock for the earliest open month whose cutoff
    has passed (months lock in order). No duplicate while one is queued or running (D4)."""
    from django.conf import settings

    from apps.planning.models import FiscalYear, ReportingPeriod

    if not settings.AUTO_LOCK_ENABLED:
        return 0  # D49: months are closed by hand only

    queued = 0
    now = timezone.now()
    for fy in FiscalYear.objects.filter(status=FiscalYear.Status.OPEN, profile__auto_lock=True):
        first_open = fy.periods.filter(status=ReportingPeriod.Status.OPEN).order_by("month_index").first()
        if first_open is None or first_open.cutoff_at > now:
            continue
        pending = Job.objects.filter(
            kind=Job.Kind.LOCK_PERIOD,
            status__in=[Job.Status.QUEUED, Job.Status.RUNNING],
            params__period_id=str(first_open.pk),
        )
        if not pending.exists():
            enqueue(Job.Kind.LOCK_PERIOD, {"period_id": str(first_open.pk), "auto": True})
            queued += 1
    return queued
