"""Deleting an office with everything recorded for it (Settings → Offices → Delete)."""

import pytest
from django.db import DatabaseError, transaction

from apps.audit.models import AuditLog
from apps.planning.models import Activity, Plan
from apps.reporting.models import ActivityActual
from apps.results.models import PeriodResult
from apps.structure.models import Office
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def closed_january(w):
    boss = client(w, "boss")
    jan = w["periods"][1]["id"]
    base = {"office": str(w["div"].id), "period": jan}
    boss.post(
        "/api/v1/reports/save",
        {**base, "activities": [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "2"}]},
    )
    boss.post("/api/v1/reports/submit", base)
    assert boss.post(f"/api/v1/periods/{jan}/lock").status_code == 200
    return boss, jan


def test_preview_then_delete_a_division_with_a_closed_month():
    w = reporting_world()
    boss, jan = closed_january(w)
    div = str(w["div"].id)
    preview = boss.get(f"/api/v1/offices/{div}/delete-preview").json()
    assert preview["offices"] == 2 and [o["code"] for o in preview["offices_beneath"]] == ["UNIT"]
    assert preview["plans"] == 1 and preview["activities"] == 3 and preview["results"] >= 1
    assert preview["closed_months"] == 1
    r = boss.delete(f"/api/v1/offices/{div}?everything=1")
    assert r.status_code == 200, r.content
    with context.agency_context(w["agency"].id):
        assert not Office.objects.filter(code__in=["DIV", "UNIT"]).exists()
        assert not Plan.objects.exists() and not ActivityActual.objects.exists()
        # The closed month was recalculated: nothing is left to report on, so no frozen rows remain.
        assert not PeriodResult.objects.filter(period_id=jan).exists()
        row = AuditLog.objects.filter(action="delete", entity_type="office").latest("at")
        assert row.before["offices"] == 2 and row.before["offices_beneath"] == ["UNIT"]
    # The closed-month guard is back in force after the deletion.
    assert boss.get("/api/v1/offices").status_code == 200


def test_deleting_the_office_that_carries_out_an_activity_keeps_the_owner_plan():
    w = reporting_world()
    boss = client(w, "boss")
    r = boss.delete(f"/api/v1/offices/{w['unit'].id}?everything=1")
    assert r.status_code == 200, r.content
    with context.agency_context(w["agency"].id):
        a = Activity.objects.get(code="A")
        assert a.implementing_office_id is None and a.plan.office_id == w["div"].id


def test_totals_above_stay_right_after_deleting_an_office_without_data():
    w = reporting_world()
    boss, jan = closed_january(w)
    with context.agency_context(w["agency"].id):
        before = {
            (str(r.office_id), r.view): r.cum_actual for r in PeriodResult.objects.filter(period_id=jan)
        }
    assert boss.delete(f"/api/v1/offices/{w['other'].id}?everything=1").status_code == 200
    with context.agency_context(w["agency"].id):
        after = {(str(r.office_id), r.view): r.cum_actual for r in PeriodResult.objects.filter(period_id=jan)}
    assert after == before
    # The closed-month guard is back in force: January's figures still cannot be changed.
    with context.agency_context(w["agency"].id), pytest.raises(DatabaseError), transaction.atomic():
        ActivityActual.objects.filter(period_id=jan).update(actual_qty=9)


def test_the_top_office_and_other_users_are_refused():
    w = reporting_world()
    boss, div = client(w, "boss"), client(w, "div")
    assert boss.delete(f"/api/v1/offices/{w['root'].id}?everything=1").status_code == 400
    assert boss.get(f"/api/v1/offices/{w['root'].id}/delete-preview").status_code == 400
    assert div.get(f"/api/v1/offices/{w['unit'].id}/delete-preview").status_code == 403
    assert div.delete(f"/api/v1/offices/{w['unit'].id}?everything=1").status_code == 403
