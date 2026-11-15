"""P6.3 reporting API and P6.4 edit rules."""

import pytest

from apps.planning.models import ReportingPeriod
from apps.reporting.models import ActivityActual
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


@pytest.fixture
def w():
    return reporting_world()


def base(w, office="div", month=1):
    return {"office": str(w[office].id), "period": w["periods"][month]["id"]}


def save(c, w, acts, office="div", month=1, **extra):
    payload = {
        **base(w, office, month),
        "activities": [{"lineage_id": w["acts"][code]["lineage_id"], **v} for code, v in acts.items()],
        **extra,
    }
    return c.post("/api/v1/reports/save", payload)


def month(c, w, office="div", m=1, view="owner"):
    return c.get("/api/v1/reports", office=str(w[office].id), period=w["periods"][m]["id"], view=view).json()


def test_month_view_figures(w):
    div = client(w, "div")
    save(div, w, {"A": {"actual": "2"}}, month=1)
    save(div, w, {"A": {"actual": "2", "remarks": "two visits"}, "B": {"actual": "1"}}, month=2)
    feb = month(div, w, m=2)
    rows = {a["code"]: a for a in feb["activities"]}
    a = rows["A"]
    assert (a["target_month"], a["cum_target"], a["prev_cum_actual"], a["actual"]) == ("3", "5", "2", "2")
    assert (
        a["remarks"] == "two visits"
        and a["owner_office"]["code"] == "DIV"
        and a["implementing_office"]["code"] == "UNIT"
    )
    assert a["behind"] is True and rows["B"]["behind"] is True and rows["C"]["behind"] is False
    assert all(r["editable"] for r in feb["activities"])
    # Live result for February = the worked example's February figures.
    r = feb["result"]
    assert (round(float(r["cum_plan"]), 6), round(float(r["cum_actual"]), 6)) == (0.45, 0.315)
    assert r["status"] == "DELAYED"
    assert feb["submission"]["status"] == "draft" and feb["can_submit"] is True


def test_read_only_and_out_of_scope(w):
    assert save(client(w, "viewer"), w, {"A": {"actual": "1"}}).status_code == 403
    assert (
        client(w, "other")
        .get("/api/v1/reports", **{"office": str(w["div"].id), "period": w["periods"][1]["id"]})
        .status_code
        == 404
    )
    v = month(client(w, "viewer"), w)
    assert not any(r["editable"] for r in v["activities"]) and v["can_submit"] is False


def test_field_unit_reports_its_own_activity_only(w):
    unit = client(w, "unit")
    assert save(unit, w, {"A": {"actual": "2"}}, office="unit", view="implementing").status_code == 200
    assert save(unit, w, {"B": {"actual": "1"}}, office="unit", view="implementing").status_code == 404
    assert (
        client(w, "unit")
        .get("/api/v1/reports", office=str(w["div"].id), period=w["periods"][1]["id"])
        .status_code
        == 404
    )


def test_locked_period_refuses_saves(w):
    with context.agency_context(w["agency"].id):
        ReportingPeriod.objects.filter(pk=w["periods"][1]["id"]).update(status="locked")
    r = save(client(w, "div"), w, {"A": {"actual": "1"}})
    assert r.status_code == 409 and r.json()["code"] == "period_locked"


def test_submit_needs_delay_reasons_then_locks_edits_until_returned(w):
    div, boss = client(w, "div"), client(w, "boss")
    save(div, w, {"A": {"actual": "1"}})  # planned 2: behind
    r = div.post("/api/v1/reports/submit", base(w))
    assert r.status_code == 400 and {p["code"] for p in r.json()["problems"]} == {"delay_reason"}
    save(div, w, {"A": {"delay_reason": "Rain delayed two visits"}})
    sub = div.post("/api/v1/reports/submit", base(w)).json()
    assert sub["submission"]["status"] == "submitted" and sub["can_submit"] is False
    r = save(div, w, {"A": {"actual": "2"}})
    assert r.status_code == 409 and r.json()["code"] == "submission_closed"
    # Field unit is blocked too: the owner's report is closed.
    assert (
        save(client(w, "unit"), w, {"A": {"actual": "2"}}, office="unit", view="implementing").status_code
        == 409
    )
    assert div.post("/api/v1/reports/return", {**base(w), "note": "x"}).status_code == 403
    assert boss.post("/api/v1/reports/return", base(w)).status_code == 400  # a note is required
    back = boss.post("/api/v1/reports/return", {**base(w), "note": "Check the visit count"}).json()
    assert (
        back["submission"]["status"] == "returned"
        and back["submission"]["return_note"] == "Check the visit count"
    )
    assert save(div, w, {"A": {"actual": "2"}}).status_code == 200


def test_bad_numbers_and_unknown_rows(w):
    div = client(w, "div")
    assert save(div, w, {"A": {"actual": "-1"}}).json()["code"] == "bad_number"
    assert save(div, w, {"A": {"actual": "lots"}}).json()["code"] == "bad_number"
    r = div.post(
        "/api/v1/reports/save",
        {**base(w), "activities": [{"lineage_id": str(w["agency"].id), "actual": "1"}]},
    )
    assert r.status_code == 404


def test_preview_uses_unsaved_numbers_and_stores_nothing(w):
    div = client(w, "div")
    r = div.post(
        "/api/v1/reports/preview",
        {**base(w), "activities": [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "2"}]},
    ).json()
    assert round(float(r["result"]["cum_actual"]), 6) == 0.12 and r["result"]["status"] == "ON-TIME"
    with context.agency_context(w["agency"].id):
        assert ActivityActual.objects.count() == 0


def test_implementing_view_lists_activities_owned_by_other_offices(w):
    unit = client(w, "unit")
    v = month(unit, w, office="unit", view="implementing")
    assert [a["code"] for a in v["activities"]] == ["A"]
    assert v["activities"][0]["owner_office"]["code"] == "DIV" and v["activities"][0]["editable"]
    assert v["can_submit"] is False  # the owning division submits its month
    save(unit, w, {"A": {"actual": "2"}}, office="unit", view="implementing")
    after = month(unit, w, office="unit", view="implementing")
    assert after["activities"][0]["actual"] == "2"
    assert round(float(after["result"]["cum_actual"]), 6) == 0.2  # A alone: 2 of 10
