"""P6.6 (MOV required) and P6.7 (actual amounts)."""

import pytest

from tests.reporting_helpers import client, reporting_world, upload

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def tmp_storage(tmp_path, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }


@pytest.fixture
def w():
    return reporting_world()


def base(w, m=1):
    return {"office": str(w["div"].id), "period": w["periods"][m]["id"]}


def save(c, w, acts, m=1):
    return c.post(
        "/api/v1/reports/save",
        {
            **base(w, m),
            "activities": [{"lineage_id": w["acts"][k]["lineage_id"], **v} for k, v in acts.items()],
        },
    )


def test_mov_required_blocks_rows_with_accomplishments_but_no_file(w):
    boss, div = client(w, "boss"), client(w, "div")
    boss.patch(f"/api/v1/scoring-profiles/{w['fy']['profile_id']}", {"mov_required": True})
    assert div.get("/api/v1/reports", **base(w)).json()["mov_required"] is True
    save(div, w, {"A": {"actual": "2"}, "B": {"actual": "0"}})
    r = div.post("/api/v1/reports/submit", base(w))
    assert r.status_code == 400
    problems = r.json()["problems"]
    assert [(p["code"], p["row"]) for p in problems] == [("mov_required", w["acts"]["A"]["lineage_id"])]
    assert upload(div, w, act="A").status_code == 201
    assert div.post("/api/v1/reports/submit", base(w)).json()["submission"]["status"] == "submitted"


def test_mov_not_required_by_default(w):
    div = client(w, "div")
    save(div, w, {"A": {"actual": "2"}})
    assert div.post("/api/v1/reports/submit", base(w)).status_code == 200


def test_actual_amounts_replace_the_estimate(w):
    boss, div = client(w, "boss"), client(w, "div")
    assert div.get("/api/v1/reports", **base(w)).json()["show_amounts"] is False
    boss.patch(f"/api/v1/scoring-profiles/{w['fy']['profile_id']}", {"show_actual_amounts": True})
    month = div.get("/api/v1/reports", **base(w)).json()
    assert month["show_amounts"] is True and month["result"]["funds_used_actual"] is None
    save(div, w, {"A": {"actual": "2", "actual_amount": "110000"}})
    save(div, w, {"B": {"actual": "1", "actual_amount": "70000.50"}}, m=2)
    feb = div.get("/api/v1/reports", **base(w, 2)).json()["result"]
    assert feb["funds_used_actual"] == "180000.50"
    assert feb["funds_remaining"] == "819999.50"  # 1,000,000 - actual, not the estimate
    assert save(div, w, {"A": {"actual_amount": "-5"}}).json()["code"] == "bad_number"
