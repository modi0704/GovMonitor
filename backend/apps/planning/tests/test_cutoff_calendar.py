import pytest

from apps.planning.models import ReportingPeriod
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


def test_agency_admin_moves_a_cutoff_of_an_open_month():
    agency = make_agency("alpha")
    root = make_root(agency)
    assign(make_user(agency, "boss@a.gov"), root, "admin")
    assign(make_user(agency, "mid@a.gov"), make_office(root, "D"), "admin")
    boss = Json(api_client("boss@a.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    jan, feb = fy["periods"][0], fy["periods"][1]
    r = boss.patch(f"/api/v1/periods/{jan['id']}", {"cutoff_at": "2026-02-20T17:00:00+08:00"})
    assert r.status_code == 200 and r.json()["cutoff_at"] == "2026-02-20T09:00:00+00:00"
    assert (
        boss.patch(f"/api/v1/periods/{jan['id']}", {"cutoff_at": "2026-01-15T17:00:00+08:00"}).status_code
        == 400
    )
    assert boss.patch(f"/api/v1/periods/{jan['id']}", {"cutoff_at": "soon"}).status_code == 400
    assert (
        Json(api_client("mid@a.gov"))
        .patch(f"/api/v1/periods/{feb['id']}", {"cutoff_at": "2026-03-20T00:00:00Z"})
        .status_code
        == 403
    )
    with context.agency_context(agency.id):
        ReportingPeriod.objects.filter(pk=feb["id"]).update(status="locked")
    assert (
        boss.patch(f"/api/v1/periods/{feb['id']}", {"cutoff_at": "2026-03-20T00:00:00Z"}).status_code == 409
    )
