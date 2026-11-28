"""D49: one monitoring officer on one PC — the shipped defaults and the steps the app now does by
itself (Save as final, Change plan, Change results, Excel method for new years). The test settings
run with every switchable feature on; each test here switches back to the shipped defaults."""

import datetime

import pytest
from django.utils import timezone

from apps.jobs import worker
from apps.planning.models import Plan, ReportingPeriod, ScoringProfile
from apps.results.models import PeriodResult
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def test_the_shipped_settings_are_for_one_user_on_one_pc():
    import config.settings.base as base

    assert base.LOGIN_DISABLED is True  # no sign-in; './run.sh login on' brings it back
    assert base.LICENCE_ENFORCED is False
    assert base.PLATFORM_ENABLED is False
    assert base.ALERTS_ENABLED is False
    assert base.AUTO_LOCK_ENABLED is False
    assert base.OFFICE_GROUPS_ENABLED is False


def test_save_as_final_makes_a_plan_final_in_one_step():
    w = reporting_world()
    boss = client(w, "boss")
    plan = boss.post(
        "/api/v1/plans", {"office_id": str(w["other"].id), "fiscal_year_id": w["fy"]["id"]}
    ).json()
    row = {"client_key": "x", "row_kind": "activity", "code": "X", "title": "Visits", "sort_order": 0,
           "measure_type": "quantity", "unit": "visit", "annual_target": "12", "total_cost": "1200",
           "targets": ["1"] * 12}  # fmt: skip
    boss.post(f"/api/v1/plans/{plan['id']}/save", {"rows": [row]})
    r = boss.post(f"/api/v1/plans/{plan['id']}/finalize")
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert boss.post(f"/api/v1/plans/{plan['id']}/finalize").json()["status"] == "approved"  # no-op
    # A plan with blocking problems is not made final.
    empty = boss.post(
        "/api/v1/plans", {"office_id": str(w["unit"].id), "fiscal_year_id": w["fy"]["id"]}
    ).json()
    r = boss.post(f"/api/v1/plans/{empty['id']}/finalize")
    assert r.status_code == 400 and r.json()["code"] == "invalid_plan"


def test_change_plan_then_save_as_final_keeps_closed_months():
    w = reporting_world()
    boss = client(w, "boss")
    jan = w["periods"][1]["id"]
    base = {"office": str(w["div"].id), "period": jan}
    boss.post(
        "/api/v1/reports/save",
        {**base, "activities": [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "2"}]},
    )
    boss.post("/api/v1/reports/submit", base)
    boss.post(f"/api/v1/periods/{jan}/lock")
    with context.agency_context(w["agency"].id):
        frozen = {(str(r.office_id), r.view): r.cum_plan for r in PeriodResult.objects.filter(period_id=jan)}
    draft = boss.post(f"/api/v1/plans/{w['plan']['id']}/change").json()
    assert draft["status"] == "draft" and draft["version"] == 2
    assert boss.post(f"/api/v1/plans/{w['plan']['id']}/change").json()["id"] == draft["id"]  # same copy
    rows = draft["rows"]
    a = next(r for r in rows if r["code"] == "A")
    boss.post(
        f"/api/v1/plans/{draft['id']}/save",
        {"rows": [{**a, "annual_target": "20", "targets": ["2", "3", "15"] + ["0"] * 9}]},
    )
    assert boss.post(f"/api/v1/plans/{draft['id']}/finalize").json()["status"] == "approved"
    with context.agency_context(w["agency"].id):
        assert Plan.objects.get(pk=w["plan"]["id"]).status == "superseded"
        after = {(str(r.office_id), r.view): r.cum_plan for r in PeriodResult.objects.filter(period_id=jan)}
    assert after == frozen  # January stays as it was closed


def test_change_results_reopens_a_month_marked_done():
    w = reporting_world()
    boss = client(w, "boss")
    base = {"office": str(w["div"].id), "period": w["periods"][1]["id"]}
    boss.post(
        "/api/v1/reports/save",
        {**base, "activities": [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "2"}]},
    )
    boss.post("/api/v1/reports/submit", base)
    r = boss.post("/api/v1/reports/reopen", base)
    assert r.status_code == 200 and r.json()["submission"]["status"] == "draft"
    assert boss.post("/api/v1/reports/reopen", base).status_code == 409  # not marked done any more
    boss.post("/api/v1/reports/submit", base)
    boss.post(f"/api/v1/periods/{base['period']}/lock")
    assert boss.post("/api/v1/reports/reopen", base).status_code == 409  # a closed month stays closed


def test_a_missing_or_expired_licence_never_makes_the_app_read_only(settings, tmp_path):
    w = reporting_world()
    boss = client(w, "boss")
    settings.DEPLOYMENT_MODE = "single"
    settings.LICENCE_FILE = str(tmp_path / "missing.json")
    from apps.tenancy import licence

    licence._cache.clear()
    settings.LICENCE_ENFORCED = True
    assert (
        boss.post("/api/v1/offices", {"parent_id": str(w["root"].id), "name": "N", "code": "N1"}).status_code
        == 403
    )
    settings.LICENCE_ENFORCED = False
    licence._cache.clear()
    assert (
        boss.post("/api/v1/offices", {"parent_id": str(w["root"].id), "name": "N", "code": "N1"}).status_code
        == 201
    )
    me = boss.get("/api/v1/me").json()
    assert me["licence"]["read_only"] is False and me["licence"]["message"] == ""


def test_platform_alerts_auto_lock_and_groups_are_off_by_default(settings):
    w = reporting_world()
    boss = client(w, "boss")
    settings.PLATFORM_ENABLED = False
    assert boss.c.get("/platform/api/me").status_code == 404
    settings.ALERTS_ENABLED = False
    settings.AUTO_LOCK_ENABLED = False
    with context.agency_context(w["agency"].id):
        ScoringProfile.objects.update(auto_lock=True)
        ReportingPeriod.objects.update(cutoff_at=timezone.now() - datetime.timedelta(days=1))
    assert worker.schedule_pass() == 0  # neither an alert scan nor an automatic close is queued
    settings.OFFICE_GROUPS_ENABLED = False
    boss.post("/api/v1/groups", {"name": "Together"})
    sets = boss.get("/api/v1/rankings", period=w["periods"][1]["id"]).json()["sets"]
    assert sets and all(s["kind"] == "children" for s in sets)
