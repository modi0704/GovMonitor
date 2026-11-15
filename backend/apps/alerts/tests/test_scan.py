"""P11.2 / P11.5: every alert trigger with a frozen clock, deduplication and the scheduler.

The world (tests.reporting_helpers): ROOT (boss = agency admin) ─ DIV (div admin, viewer read-only;
owns the plan; activity A is implemented by UNIT) ─ UNIT (unit admin); OTHER (other admin).
January's cutoff is set to 5 February 2026, 23:59 Manila time.
"""

import datetime
import zoneinfo

import pytest

from apps.alerts import services
from apps.alerts.jobs import schedule_alert_scan
from apps.alerts.models import Notification
from apps.jobs.models import Job
from apps.planning.models import ReportingPeriod
from apps.reporting.models import OfficeSubmission
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db
MANILA = zoneinfo.ZoneInfo("Asia/Manila")
CUTOFF = datetime.datetime(2026, 2, 5, 23, 59, tzinfo=MANILA)


def at(day, hour=9, month=2):
    return datetime.datetime(2026, month, day, hour, 0, tzinfo=MANILA)


@pytest.fixture
def w():
    world = reporting_world()
    with context.agency_context(world["agency"].id):
        ReportingPeriod.objects.filter(pk=world["periods"][1]["id"]).update(cutoff_at=CUTOFF)
        # Later months' cutoffs are far away, so only January is in play.
        ReportingPeriod.objects.exclude(pk=world["periods"][1]["id"]).update(
            cutoff_at=datetime.datetime(2027, 1, 1, tzinfo=MANILA)
        )
        Notification.objects.all().delete()  # the plan approval at setup notified the boss
    return world


def scan(w, now):
    with context.agency_context(w["agency"].id):
        return services.scan(now=now)


def inbox(w, who, type_=None) -> list:
    with context.agency_context(w["agency"].id):
        qs = Notification.objects.filter(user__email=f"{who}@{w['code']}.gov")
        if type_:
            qs = qs.filter(type=type_)
        return list(qs.order_by("created_at").values_list("title", flat=True))


def total(w) -> int:
    with context.agency_context(w["agency"].id):
        return Notification.objects.count()


def test_reminders_n_days_before_the_cutoff_go_to_the_office_admins_once(w):
    assert scan(w, at(31, month=1))["cutoff_reminder"] == 1  # 5 Feb is 5 days after 31 Jan
    assert inbox(w, "div") == ["DIV: January 2026 report due in 5 days"]
    assert inbox(w, "boss") == inbox(w, "unit") == inbox(w, "viewer") == []
    scan(w, at(31, hour=15, month=1))  # same day again: nothing new
    assert len(inbox(w, "div")) == 1
    scan(w, at(1))  # 4 days before: not a reminder day (5, 1)
    assert len(inbox(w, "div")) == 1
    scan(w, at(4))
    assert inbox(w, "div")[-1] == "DIV: January 2026 report due tomorrow"


def test_no_reminder_once_the_office_has_submitted(w):
    with context.agency_context(w["agency"].id):
        OfficeSubmission.objects.create(office=w["div"], period_id=w["periods"][1]["id"], status="submitted")
    scan(w, at(31, month=1))
    scan(w, at(6))
    assert inbox(w, "div") == []


def test_cutoff_passed_goes_to_office_admins_and_agency_admins_once(w):
    scan(w, at(6))
    assert inbox(w, "div", "cutoff_passed") == ["DIV: January 2026 report is late"]
    assert inbox(w, "boss", "cutoff_passed") == ["DIV: January 2026 report is late"]
    assert inbox(w, "other") == [] and inbox(w, "viewer") == []
    before = total(w)
    scan(w, at(7))
    scan(w, at(8))
    assert total(w) == before


def test_missing_accomplishments_three_days_before_cutoff(w):
    # January targets: only activity A (2 units), owned by DIV and carried out by UNIT.
    scan(w, at(2))
    assert inbox(w, "div", "missing_actuals") == ["DIV: 1 activity has no accomplishment for January 2026"]
    assert inbox(w, "unit", "missing_actuals") == ["UNIT: 1 activity has no accomplishment for January 2026"]
    assert inbox(w, "boss", "missing_actuals") == []

    # Once reported, the next month's check finds nothing for A.
    w2_period = w["periods"][1]["id"]
    w["boss"].post(
        "/api/v1/reports/save",
        {"office": str(w["div"].id), "period": w2_period,
         "activities": [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "2"}]},
    )  # fmt: skip
    with context.agency_context(w["agency"].id):
        Notification.objects.all().delete()
    scan(w, at(2))
    assert inbox(w, "div", "missing_actuals") == []


def test_delay_after_locking_goes_to_everyone_up_the_tree(w):
    # January: plan 12%, nothing done → variance −12 points, below −5.
    assert w["boss"].post(f"/api/v1/periods/{w['periods'][1]['id']}/lock").status_code == 200
    now = datetime.datetime.now(tz=MANILA)
    scan(w, now)
    title = "DIV is 12.00 points behind plan (January 2026)"
    for who in ("div", "viewer"):
        assert inbox(w, who, "delayed") == [title], who
    # ROOT rolls DIV up, so it is behind too: the agency administrator hears about both.
    assert sorted(inbox(w, "boss", "delayed")) == [title, "ROOT is 12.00 points behind plan (January 2026)"]
    assert inbox(w, "other", "delayed") == [] and inbox(w, "unit", "delayed") == []
    before = total(w)
    scan(w, now + datetime.timedelta(days=1))
    assert total(w) == before
    # A higher threshold stops it (the alert rule decides what counts as a delay).
    w["boss"].patch("/api/v1/alert-rules", {"delay_threshold": "0.2"})
    with context.agency_context(w["agency"].id):
        Notification.objects.filter(type="delayed").delete()
    scan(w, now)
    assert inbox(w, "div", "delayed") == []


def test_events_return_lock_unlock_and_plan_submitted(w):
    period = w["periods"][1]["id"]
    base = {"office": str(w["div"].id), "period": period}
    acts = [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "2"}]
    w["boss"].post("/api/v1/reports/save", {**base, "activities": acts})
    assert w["boss"].post("/api/v1/reports/submit", base).status_code == 200
    assert w["boss"].post("/api/v1/reports/return", {**base, "note": "Attach the list"}).status_code == 200
    [returned] = inbox(w, "div", "submission_returned")
    assert returned == "DIV: January 2026 report returned"
    assert inbox(w, "boss", "submission_returned") == []

    assert w["boss"].post(f"/api/v1/periods/{period}/lock").status_code == 200
    assert inbox(w, "div", "period_locked") == ["January 2026 is locked"]
    assert w["boss"].post(f"/api/v1/periods/{period}/unlock", {"reason": "Late file"}).status_code == 200
    assert inbox(w, "div", "period_unlocked") == ["January 2026 was reopened"]

    # A plan submitted for approval tells the agency administrators.
    fy = w["boss"].post("/api/v1/fiscal-years", {"label": "2027", "start_year": 2027}).json()
    other = client(w, "other")
    plan = other.post("/api/v1/plans", {"office_id": str(w["other"].id), "fiscal_year_id": fy["id"]}).json()
    from tests.plan_helpers import worked_example_rows

    other.post(f"/api/v1/plans/{plan['id']}/save", {"rows": worked_example_rows()})
    assert other.post(f"/api/v1/plans/{plan['id']}/submit").status_code == 200
    assert inbox(w, "boss", "plan_submitted") == ["OTHER: plan 2027 v1 waits for approval"]
    assert inbox(w, "other", "plan_submitted") == []


def test_the_scan_is_queued_once_a_day_after_six_local(w):
    with context.agency_context(w["agency"].id):
        assert schedule_alert_scan(now=at(10, hour=5)) == 0  # too early
        assert schedule_alert_scan(now=at(10, hour=7)) == 1
        assert schedule_alert_scan(now=at(10, hour=8)) == 0  # already today
        Job.objects.filter(kind="alert_scan").update(created_at=at(10, hour=7))
        assert schedule_alert_scan(now=at(11, hour=7)) == 1  # next day


def test_exit_check_a_scan_run_twice_creates_no_duplicates(w):
    """Every scheduled trigger at once — January locked and behind plan, February late, March due in
    3 days with accomplishments missing — then the same scan again, the next day, and a replayed
    event: no notification is created twice."""
    p = w["periods"]
    w["boss"].patch("/api/v1/alert-rules", {"remind_days_before": [3]})
    assert w["boss"].post(f"/api/v1/periods/{p[1]['id']}/lock").status_code == 200
    now = datetime.datetime.now(tz=MANILA)
    with context.agency_context(w["agency"].id):
        ReportingPeriod.objects.filter(pk=p[2]["id"]).update(cutoff_at=now - datetime.timedelta(days=1))
        ReportingPeriod.objects.filter(pk=p[3]["id"]).update(
            cutoff_at=datetime.datetime.combine(
                (now + datetime.timedelta(days=3)).date(), datetime.time(23, 59), tzinfo=MANILA
            )
        )
    first = scan(w, now)
    assert first["delayed"] > 0 and first["cutoff_passed"] > 0
    assert first["cutoff_reminder"] > 0 and first["missing_actuals"] > 0
    before = total(w)
    second = scan(w, now)
    assert all(v == 0 for v in second.values()), second
    scan(w, now + datetime.timedelta(hours=6))
    assert total(w) == before
    with context.agency_context(w["agency"].id):
        period = ReportingPeriod.objects.get(pk=p[1]["id"])
        assert services.period_locked(period) == 0  # the lock event replayed
    assert total(w) == before
