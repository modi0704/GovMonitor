"""P8.8: the agency dashboard at the D13 sizing ceiling (500 offices, 5,000 activities) answers in
under 2 seconds for an open month; queries do not grow with size; live results are cached until
the data changes."""

import os
import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.results import read
from tests.factories import Json, api_client
from tests.perf_world import build
from tests.reporting_helpers import client, reporting_world

pytestmark = [pytest.mark.django_db, pytest.mark.perf]
# Slower CI machines may scale the budget (e.g. PERF_FACTOR=1.5); the product target is 2 s.
BUDGET = 2.0 * float(os.environ.get("PERF_FACTOR", "1"))


def dashboard(c, office, period):
    with CaptureQueriesContext(connection) as q:
        start = time.perf_counter()
        r = c.get("/api/v1/dashboard", office=str(office.id), period=str(period.id))
        elapsed = time.perf_counter() - start
    assert r.status_code == 200
    return r.json(), elapsed, len(q.captured_queries)


def test_ceiling_dashboard_under_two_seconds_and_constant_queries():
    read.clear_live_cache()
    small = reporting_world("small")
    _, _, small_queries = dashboard(
        client(small, "boss"), small["root"], type("P", (), {"id": small["periods"][2]["id"]})
    )
    read.clear_live_cache()
    w = build()
    assert (w["offices"], w["activities"]) == (501, 5000)
    c = Json(api_client("boss@perf.gov"))
    data, elapsed, queries = dashboard(c, w["root"], w["periods"][6])
    assert data["has_result"] and len(data["children"]) == 10
    assert elapsed < BUDGET, f"uncached dashboard took {elapsed:.2f}s"
    assert queries <= small_queries + 5, (queries, small_queries)  # does not grow with the agency's size


def test_live_results_are_cached_until_data_changes():
    read.clear_live_cache()
    w = reporting_world()
    boss, div = client(w, "boss"), client(w, "div")
    feb = type("P", (), {"id": w["periods"][2]["id"]})
    first, _, cold = dashboard(boss, w["root"], feb)
    again, _, warm = dashboard(boss, w["root"], feb)
    assert again["headline"] == first["headline"] and warm < cold
    div.post(
        "/api/v1/reports/save",
        {
            "office": str(w["div"].id),
            "period": w["periods"][2]["id"],
            "activities": [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "3"}],
        },
    )
    changed, _, _ = dashboard(boss, w["root"], feb)
    assert changed["headline"]["cum_actual"] != first["headline"]["cum_actual"]


def test_load_at_the_ceiling_monthly_grid_and_lock():
    """P14.3: at the D13 ceiling — open and save a division's monthly grid (70 activities) in under
    2 seconds each, and lock a month for the whole agency in under 60 seconds."""
    from apps.planning.models import Activity, Plan
    from apps.results.models import PeriodResult
    from apps.structure.models import Office
    from apps.tenancy import context

    read.clear_live_cache()
    w = build("load")
    c = Json(api_client("boss@load.gov"))
    with context.agency_context(w["agency"].id):
        division = Office.objects.filter(code="D3-4").get()
        plan = Plan.objects.get(office=division)
        lineages = list(
            Activity.objects.filter(plan=plan, row_kind="activity").values_list("lineage_id", flat=True)
        )
    assert len(lineages) == 70
    month = {"office": str(division.id), "period": str(w["periods"][7].id)}

    start = time.perf_counter()
    r = c.get("/api/v1/reports", **month)
    opened = time.perf_counter() - start
    assert r.status_code == 200, r.content[:200]

    rows = [{"lineage_id": str(lin), "actual": "1", "remarks": "Done"} for lin in lineages]
    start = time.perf_counter()
    r = c.post("/api/v1/reports/save", {**month, "activities": rows})
    saved = time.perf_counter() - start
    assert r.status_code == 200, r.content[:200]

    start = time.perf_counter()
    r = c.post(f"/api/v1/periods/{w['periods'][1].id}/lock")
    locked = time.perf_counter() - start
    assert r.status_code == 200, r.content[:200]
    with context.agency_context(w["agency"].id):
        frozen = PeriodResult.objects.filter(period=w["periods"][1]).count()
    print(
        f"\nceiling: grid opened {opened:.2f}s, 70 rows saved {saved:.2f}s, "
        f"month locked {locked:.1f}s ({frozen} results)"
    )
    assert opened < BUDGET, f"monthly grid took {opened:.2f}s to open"
    assert saved < BUDGET, f"saving 70 rows took {saved:.2f}s"
    assert locked < 60 * float(os.environ.get("PERF_FACTOR", "1")), f"lock took {locked:.1f}s"
    assert frozen > 500
