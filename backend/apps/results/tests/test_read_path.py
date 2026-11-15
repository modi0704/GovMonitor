"""P7.8 read path and the Phase 7 exit checks."""

import pytest

from apps.planning.models import ReportingPeriod
from apps.results.read import get_agency_results, get_result
from apps.tenancy import context
from tests.plan_helpers import months
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def period(w, m):
    return ReportingPeriod.objects.select_related("fiscal_year__profile").get(pk=w["periods"][m]["id"])


def test_locked_results_never_change_after_profile_or_plan_changes():
    w = reporting_world()
    boss, div = client(w, "boss"), client(w, "div")
    a = w["acts"]["A"]["lineage_id"]
    div.post(
        "/api/v1/reports/save",
        {
            "office": str(w["div"].id),
            "period": w["periods"][1]["id"],
            "activities": [{"lineage_id": a, "actual": "1"}],
        },
    )
    with context.agency_context(w["agency"].id):
        live = get_result(period(w, 1), w["div"])
    assert live.final is False and live.label == "PROVISIONAL"
    assert float(live.cum_actual) == 0.06 and live.status_label == "DELAYED" and live.status_kind == "delayed"

    boss.post(f"/api/v1/periods/{w['periods'][1]['id']}/lock")
    with context.agency_context(w["agency"].id):
        frozen = get_result(period(w, 1), w["div"])
    assert frozen.final is True and frozen.label == "FINAL" and float(frozen.cum_actual) == 0.06

    # Change the scoring rules (ceiling, tolerance, labels) and approve a revised plan.
    r = boss.patch(
        f"/api/v1/scoring-profiles/{w['fy']['profile_id']}",
        {"on_time_tolerance": "0.10", "label_delayed": "BEHIND", "weighting": "equal", "confirm": True},
    )
    assert r.status_code == 200
    v2 = boss.post(f"/api/v1/plans/{w['plan']['id']}/revise").json()
    a_row = next(x for x in v2["rows"] if x["code"] == "A")
    boss.post(
        f"/api/v1/plans/{v2['id']}/save",
        {"rows": [{"id": a_row["id"], "annual_target": "20", "targets": months([10, 5, 5])}]},
    )
    boss.post(f"/api/v1/plans/{v2['id']}/submit")
    assert boss.post(f"/api/v1/plans/{v2['id']}/approve").status_code == 200

    with context.agency_context(w["agency"].id):
        again = get_result(period(w, 1), w["div"])
        feb = get_result(period(w, 2), w["div"])  # open month: live, with the new rules and plan
    assert (again.cum_actual, again.cum_plan, again.status_label, again.plan_version) == (
        frozen.cum_actual,
        frozen.cum_plan,
        "DELAYED",
        1,
    )
    assert again.status_kind == "delayed"  # judged by the snapshot's rules, not today's
    assert feb.final is False and feb.plan_version == 2 and feb.profile["label_delayed"] == "BEHIND"

    # The monthly report of the locked month shows the frozen figures.
    month = div.get("/api/v1/reports", office=str(w["div"].id), period=w["periods"][1]["id"]).json()
    assert month["result"]["final"] is True and month["result"]["status"] == "DELAYED"


def test_agency_results_cover_both_views():
    w = reporting_world()
    with context.agency_context(w["agency"].id):
        results = get_agency_results(period(w, 1))
    assert (str(w["div"].id), "owner") in results and (str(w["unit"].id), "implementing") in results
    assert (str(w["other"].id), "owner") not in results  # no approved plan, no result
    with context.agency_context(w["agency"].id), pytest.raises(ValueError):
        get_result(period(w, 1), w["div"], "sideways")
