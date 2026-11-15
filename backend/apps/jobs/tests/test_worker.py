"""P7.7: job queue, worker loop, retries, stale re-queue, automatic locking."""

import datetime

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.jobs import worker
from apps.jobs.models import Job
from apps.planning.models import ReportingPeriod, ScoringProfile
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def tmp_storage(tmp_path, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }


def jobs(agency):
    with context.agency_context(agency.id):
        return list(Job.objects.order_by("created_at").values("kind", "status", "attempts", "result"))


def test_auto_lock_queues_and_runs_once_cutoff_has_passed():
    w = reporting_world()
    with context.agency_context(w["agency"].id):
        ScoringProfile.objects.filter(fiscal_year_id=w["fy"]["id"]).update(auto_lock=True)
        # The 2026 cutoffs are in the past "today"; start with every cutoff a week ahead.
        ReportingPeriod.objects.update(cutoff_at=timezone.now() + datetime.timedelta(days=7))
    # No cutoff has passed: nothing to do.
    call_command("run_worker", "--once")
    assert jobs(w["agency"]) == []
    with context.agency_context(w["agency"].id):
        ReportingPeriod.objects.filter(pk=w["periods"][1]["id"]).update(
            cutoff_at=timezone.now() - datetime.timedelta(hours=1)
        )
    assert worker.schedule_pass() == 1
    assert worker.schedule_pass() == 0  # no duplicate while one is queued
    assert worker.run_pending() == 1
    [job] = jobs(w["agency"])
    assert job["status"] == "done" and job["result"]["results"] > 0
    with context.agency_context(w["agency"].id):
        assert ReportingPeriod.objects.get(pk=w["periods"][1]["id"]).status == "locked"
        from apps.audit.models import AuditLog

        lock = AuditLog.objects.get(action="lock")
        assert (lock.actor_type, lock.actor_label) == ("system", "worker:lock_period")
    # February's cutoff has not passed: the scheduler stays quiet.
    assert worker.schedule_pass() == 0


def test_failures_retry_three_times_then_fail(monkeypatch):
    w = reporting_world()
    calls = []

    def boom(job):
        calls.append(job.attempts)
        raise ValueError("broken")

    monkeypatch.setitem(worker.HANDLERS, "alert_scan", boom)
    with context.agency_context(w["agency"].id):
        worker.enqueue("alert_scan")
    worker.run_pending()
    [job] = jobs(w["agency"])
    assert calls == [1, 2, 3] and job["status"] == "failed" and job["attempts"] == 3
    with context.agency_context(w["agency"].id):
        assert "ValueError: broken" in Job.objects.get().error


def test_stale_running_jobs_are_requeued():
    w = reporting_world()
    with context.agency_context(w["agency"].id):
        job = worker.enqueue("alert_scan")
        Job.objects.filter(pk=job.pk).update(
            status="running", started_at=timezone.now() - datetime.timedelta(minutes=45)
        )
        fresh = worker.enqueue("alert_scan")
        Job.objects.filter(pk=fresh.pk).update(status="running", started_at=timezone.now())
    assert worker.requeue_stale() == 1


def test_jobs_run_in_their_own_agency_context(monkeypatch):
    a, b = reporting_world("alpha"), reporting_world("beta")
    seen = []
    monkeypatch.setitem(
        worker.HANDLERS, "alert_scan", lambda job: seen.append((context.current_agency_id(), job.agency_id))
    )
    for w in (a, b):
        with context.agency_context(w["agency"].id):
            worker.enqueue("alert_scan")
    assert worker.run_pending() == 2
    assert seen == [(a["agency"].id, a["agency"].id), (b["agency"].id, b["agency"].id)]
    client(a, "boss")  # sessions unaffected
