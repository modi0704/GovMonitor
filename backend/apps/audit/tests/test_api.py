import csv
import io

import pytest

from apps.audit.models import AuditLog
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    agency = make_agency("alpha")
    root = make_root(agency)
    svc = make_office(root, "SVC")
    div = make_office(svc, "DIV")
    other = make_office(root, "OTHER")
    boss = make_user(agency, "boss@alpha.gov")
    assign(boss, root, "admin")
    assign(make_user(agency, "mid@alpha.gov"), svc, "admin")
    return {"agency": agency, "root": root, "svc": svc, "div": div, "other": other, "boss": boss}


def test_only_agency_admin_reads_the_log(world):
    assert Json(api_client("mid@alpha.gov")).get("/api/v1/audit-log").status_code == 403


def test_filters_detail_and_paging(world):
    boss = Json(api_client("boss@alpha.gov"))
    boss.patch(f"/api/v1/offices/{world['div'].id}", {"name": "Division Renamed"})
    boss.patch(f"/api/v1/offices/{world['other'].id}", {"name": "Other Renamed"})
    data = boss.get("/api/v1/audit-log", action="update", entity_type="office").json()
    assert {r["entity_id"] for r in data["results"]} == {str(world["div"].id), str(world["other"].id)}
    assert "update" in data["actions"] and "office" in data["entity_types"]
    # Office filter covers the office and everything beneath it.
    under_svc = boss.get("/api/v1/audit-log", office=str(world["svc"].id), action="update").json()["results"]
    assert [r["entity_id"] for r in under_svc] == [str(world["div"].id)]
    by_actor = boss.get("/api/v1/audit-log", actor=str(world["boss"].id)).json()["results"]
    assert all(r["actor"] == "boss@alpha.gov" for r in by_actor) and by_actor
    detail = boss.get(f"/api/v1/audit-log/{under_svc[0]['id']}").json()
    assert detail["before"] == {"name": "DIV"} and detail["after"] == {"name": "Division Renamed"}
    assert boss.get("/api/v1/audit-log", office="not-a-uuid").status_code == 404
    with context.agency_context(world["agency"].id):
        for _ in range(60):
            AuditLog.objects.create(agency=world["agency"], actor_type="system", action="bulk")
    first = boss.get("/api/v1/audit-log", action="bulk").json()
    assert len(first["results"]) == 50 and first["next_before"]
    second = boss.get("/api/v1/audit-log", action="bulk", before=first["next_before"]).json()
    assert len(second["results"]) == 10 and second["next_before"] is None


def test_date_range(world):
    boss = Json(api_client("boss@alpha.gov"))
    assert boss.get("/api/v1/audit-log", to="2000-01-01").json()["results"] == []
    assert boss.get("/api/v1/audit-log", **{"from": "2000-01-01"}).json()["results"]


def test_csv_download_is_itself_audited(world):
    boss = Json(api_client("boss@alpha.gov"))
    r = boss.get("/api/v1/audit-log/export.csv", action="login")
    assert r["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.content.decode())))
    assert rows[0][:5] == ["id", "at_utc", "actor_type", "actor", "action"]
    assert [row[4] for row in rows[1:]] == ["login"]
    export = boss.get("/api/v1/audit-log", action="export").json()["results"][0]
    assert export["entity_type"] == "audit_log"
    detail = boss.get(f"/api/v1/audit-log/{export['id']}").json()
    assert detail["after"] == {"format": "csv", "rows": 1, "filters": {"action": "login"}}
