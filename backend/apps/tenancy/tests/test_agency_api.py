import pytest

from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


def test_agency_settings_for_admin_only():
    agency = make_agency("alpha", "Alpha")
    root = make_root(agency)
    assign(make_user(agency, "boss@a.gov"), root, "admin")
    assign(make_user(agency, "mid@a.gov"), make_office(root, "S"), "admin")
    boss = Json(api_client("boss@a.gov"))
    assert boss.get("/api/v1/me").json()["agency"]["setup_complete"] is False
    r = boss.patch(
        "/api/v1/agency", {"name": "Alpha Ministry", "timezone": "Asia/Manila", "setup_complete": True}
    )
    assert r.json()["name"] == "Alpha Ministry" and r.json()["setup_complete"] is True
    assert boss.patch("/api/v1/agency", {"timezone": "Mars/Base"}).status_code == 400
    mid = Json(api_client("mid@a.gov"))
    assert mid.get("/api/v1/agency").status_code == 200
    assert mid.patch("/api/v1/agency", {"name": "Hijack"}).status_code == 403
