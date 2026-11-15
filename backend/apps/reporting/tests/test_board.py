import pytest

from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def test_submission_board():
    w = reporting_world()
    boss, div = client(w, "boss"), client(w, "div")
    jan = w["periods"][1]["id"]
    assert div.get("/api/v1/submission-board", period=jan).status_code == 403
    board = boss.get("/api/v1/submission-board", period=jan).json()
    assert [r["office"]["code"] for r in board["offices"]] == ["DIV"]
    assert board["offices"][0]["status"] == "draft" and [o["code"] for o in board["not_submitted"]] == ["DIV"]
    assert board["period"]["can_lock"] and not board["period"]["can_unlock"]
    feb = boss.get("/api/v1/submission-board", period=w["periods"][2]["id"]).json()
    assert feb["period"]["can_lock"] is False  # January is still open
    base = {"office": str(w["div"].id), "period": jan}
    div.post(
        "/api/v1/reports/save",
        {**base, "activities": [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "2"}]},
    )
    div.post("/api/v1/reports/submit", base)
    board = boss.get("/api/v1/submission-board", period=jan).json()
    assert (
        board["offices"][0]["status"] == "submitted"
        and board["offices"][0]["submitted_by"] == "div@alpha.gov"
    )
    assert board["not_submitted"] == []
    boss.post(f"/api/v1/periods/{jan}/lock")
    board = boss.get("/api/v1/submission-board", period=jan).json()
    assert board["period"]["status"] == "locked" and board["period"]["can_unlock"]
    assert board["offices"][0]["status"] == "locked"
