import pytest

from apps.planning.models import ReportingPeriod
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    agency = make_agency("alpha")
    root = make_root(agency)
    assign(make_user(agency, "boss@a.gov"), root, "admin")
    assign(make_user(agency, "mid@a.gov"), make_office(root, "D"), "admin")
    return agency


def test_create_open_close_and_read(world):
    boss = Json(api_client("boss@a.gov"))
    # D49: every new year uses the workbook method (same results as the Excel); a preset is ignored.
    r = boss.post(
        "/api/v1/fiscal-years", {"label": "2026", "start_year": 2026, "preset": "capped_with_tolerance"}
    )
    assert (
        r.status_code == 201
        and len(r.json()["periods"]) == 12
        and r.json()["preset"] == "workbook_compatible"
    )
    fy = r.json()
    assert (
        boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2027}).json()["code"]
        == "duplicate_label"
    )
    assert boss.patch(f"/api/v1/fiscal-years/{fy['id']}", {"status": "open"}).json()["status"] == "open"
    mid = Json(api_client("mid@a.gov"))
    assert [y["label"] for y in mid.get("/api/v1/fiscal-years").json()] == ["2026"]
    assert mid.post("/api/v1/fiscal-years", {"label": "x", "start_year": 2030}).status_code == 403
    assert {p["name"] for p in mid.get("/api/v1/scoring-presets").json()} == {
        "workbook_compatible",
        "capped_with_tolerance",
    }


def test_profile_changes_bump_version_and_need_confirmation_after_locking(world):
    boss = Json(api_client("boss@a.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    url = f"/api/v1/scoring-profiles/{fy['profile_id']}"
    p = boss.patch(url, {"on_time_tolerance": "0.01", "label_delayed": "BEHIND"}).json()
    assert p["version"] == 2 and p["on_time_tolerance"] == "0.0100000000" and p["preset"] == "custom"
    assert boss.patch(url, {"weighting": "random"}).status_code == 400
    assert boss.patch(url, {"cutoff_day": 31}).status_code == 400
    p = boss.patch(url, {"preset": "workbook_compatible"}).json()
    assert p["preset"] == "workbook_compatible" and p["label_delayed"] == "DELAYED" and p["version"] == 3
    assert boss.patch(url, {"preset": "workbook_compatible"}).json()["version"] == 3  # no change, no bump

    with context.agency_context(world.id):
        ReportingPeriod.objects.filter(fiscal_year_id=fy["id"], month_index=1).update(status="locked")
    r = boss.patch(url, {"cap_at_100": True})
    assert r.status_code == 409 and r.json()["code"] == "confirm_required"
    assert boss.patch(url, {"cap_at_100": True, "confirm": True}).json()["cap_at_100"] is True


def test_cutoff_day_change_moves_open_periods_only(world):
    boss = Json(api_client("boss@a.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    with context.agency_context(world.id):
        ReportingPeriod.objects.filter(fiscal_year_id=fy["id"], month_index=1).update(status="locked")
    boss.patch(f"/api/v1/scoring-profiles/{fy['profile_id']}", {"cutoff_day": 5, "confirm": True})
    periods = boss.get(f"/api/v1/fiscal-years/{fy['id']}").json()["periods"]
    assert periods[0]["cutoff_at"].startswith("2026-02-10")  # locked month keeps its cutoff
    assert periods[1]["cutoff_at"].startswith("2026-03-05")
