"""Guided steps for the monitoring administrator (progress endpoint)."""

import pytest

from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def _step(data, key):
    return next(s for s in data["steps"] if s["key"] == key)


def test_progress_walks_the_steps():
    w = reporting_world()
    boss, div = client(w, "boss"), client(w, "div")
    assert div.get("/api/v1/progress").status_code == 403
    data = boss.get("/api/v1/progress").json()
    assert data["fiscal_year"]["label"] == "2026"
    assert _step(data, "offices")["done"] and _step(data, "year")["done"]
    # DIV has an approved plan; UNIT only carries out DIV's activity; OTHER still needs a plan.
    rows = {r["office"]["code"]: r for r in data["plans"]}
    assert set(rows) == {"DIV", "OTHER"}
    assert rows["DIV"]["status"] == "approved" and rows["DIV"]["activities"] >= 1
    assert rows["OTHER"]["status"] == "none"
    assert not _step(data, "plans")["done"] and _step(data, "plans")["started"]
    assert data["current"] == "plans"
    # Monthly checklist for a chosen month: only offices with an approved plan.
    jan = w["periods"][1]["id"]
    data = boss.get("/api/v1/progress", period=jan).json()
    assert data["period"]["month_index"] == 1 and len(data["months"]) == 12
    assert [(r["office"]["code"], r["status"]) for r in data["monthly"]] == [("DIV", "not_started")]
    base = {"office": str(w["div"].id), "period": jan}
    line = {"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "2"}
    boss.post("/api/v1/reports/save", {**base, "activities": [line]})
    boss.post("/api/v1/reports/submit", base)
    data = boss.get("/api/v1/progress", period=jan).json()
    assert _step(data, "results")["done"] and data["months"][0]["offices_done"] == 1
    assert not _step(data, "review")["done"]
    boss.post(f"/api/v1/periods/{jan}/lock")
    data = boss.get("/api/v1/progress", period=jan).json()
    assert _step(data, "review")["done"]


def test_unknown_year_or_month_is_404():
    w = reporting_world()
    boss = client(w, "boss")
    assert boss.get("/api/v1/progress", fiscal_year="00000000-0000-0000-0000-000000000000").status_code == 404
    assert boss.get("/api/v1/progress", period="00000000-0000-0000-0000-000000000000").status_code == 404
