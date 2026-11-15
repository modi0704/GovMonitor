"""P11.4 / P11.5: email digests — on only with SMTP and the agency switch, per-user opt-out, at most
one per user per local day, nothing sent and nothing failing without SMTP."""

import datetime
import zoneinfo

import pytest
from django.core import mail

from apps.accounts.models import User
from apps.alerts import email
from apps.alerts.models import AlertRule, Notification
from apps.jobs import worker
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db
MANILA = zoneinfo.ZoneInfo("Asia/Manila")


def at(day, hour):
    return datetime.datetime(2026, 3, day, hour, 0, tzinfo=MANILA)


@pytest.fixture
def w(settings):
    settings.EMAIL_ENABLED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PUBLIC_URL = "https://monitor.example.gov"
    world = reporting_world()
    with context.agency_context(world["agency"].id):
        Notification.objects.all().delete()
        AlertRule.objects.create(email_enabled=True)
    return world


def notify(w, who, title, created):
    with context.agency_context(w["agency"].id):
        user = User.objects.get(email=f"{who}@{w['code']}.gov")
        n = Notification.objects.create(
            user=user, type="cutoff_reminder", title=title, link="/reports?x=1", dedupe_key=title
        )
        Notification.objects.filter(pk=n.pk).update(created_at=created)


def digests(w, now):
    with context.agency_context(w["agency"].id):
        return email.send_digests(now=now)


def test_one_digest_per_user_per_day_with_absolute_links(w):
    notify(w, "div", "DIV: report due in 5 days", at(10, 7))
    notify(w, "div", "DIV: report is late", at(10, 8))
    notify(w, "other", "OTHER: report due", at(10, 7))
    assert digests(w, at(10, 9)) == 2
    by_to = {m.to[0]: m for m in mail.outbox}
    msg = by_to["div@alpha.gov"]
    assert msg.subject == "GovMonitor: 2 new alerts"
    assert "- DIV: report due in 5 days\n  https://monitor.example.gov/reports?x=1" in msg.body
    # Later the same day: a new alert waits until tomorrow.
    notify(w, "div", "DIV: missing accomplishments", at(10, 15))
    assert digests(w, at(10, 16)) == 0
    assert digests(w, at(11, 7)) == 1
    assert mail.outbox[-1].subject == "GovMonitor: 1 new alert"
    assert digests(w, at(11, 9)) == 0  # nothing new


def test_opt_out_read_and_switched_off(w):
    notify(w, "div", "DIV: due", at(10, 7))
    notify(w, "other", "OTHER: due", at(10, 7))
    assert client(w, "div").patch("/api/v1/me", {"email_opt_out": True}).json()["email_opt_out"] is True
    client(w, "other").post("/api/v1/notifications/read-all")  # already seen in the app
    assert digests(w, at(10, 9)) == 0
    with context.agency_context(w["agency"].id):
        AlertRule.objects.update(email_enabled=False)
    client(w, "div").patch("/api/v1/me", {"email_opt_out": False})
    assert digests(w, at(10, 10)) == 0  # the agency switched email off
    assert mail.outbox == []


def test_no_smtp_sends_nothing_and_the_scan_job_still_succeeds(w, settings):
    settings.EMAIL_ENABLED = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
    notify(w, "div", "DIV: due", at(10, 7))
    assert digests(w, at(10, 9)) == 0
    with context.agency_context(w["agency"].id):
        worker.enqueue("alert_scan")
    worker.run_pending()
    with context.agency_context(w["agency"].id):
        from apps.jobs.models import Job

        job = Job.objects.get(kind="alert_scan")
        assert job.status == "done" and job.result["emails"] == 0
        assert Notification.objects.filter(emailed_at__isnull=False).count() == 0
    assert mail.outbox == []


def test_a_failing_address_does_not_stop_the_others(w, monkeypatch):
    notify(w, "div", "DIV: due", at(10, 7))
    notify(w, "other", "OTHER: due", at(10, 7))
    real = email.send_mail

    def flaky(subject, body, sender, to, **kw):
        if to == ["div@alpha.gov"]:
            raise OSError("mailbox unavailable")
        return real(subject, body, sender, to, **kw)

    monkeypatch.setattr(email, "send_mail", flaky)
    assert digests(w, at(10, 9)) == 1
    with context.agency_context(w["agency"].id):
        assert Notification.objects.get(title="DIV: due").emailed_at is None  # retried tomorrow
