"""P8.1 dashboard API."""

import pytest

from apps.structure.models import OfficeGroup, OfficeGroupMember
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


@pytest.fixture
def w():
    w = reporting_world()
    div = client(w, "div")
    for month, acts in {1: {"A": "2"}, 2: {"A": "2", "B": "1"}}.items():
        div.post(
            "/api/v1/reports/save",
            {
                "office": str(w["div"].id),
                "period": w["periods"][month]["id"],
                "activities": [
                    {"lineage_id": w["acts"][k]["lineage_id"], "actual": v} for k, v in acts.items()
                ],
            },
        )
    return w


def dash(c, w, office, m=2, **extra):
    return c.get("/api/v1/dashboard", office=str(w[office].id), period=w["periods"][m]["id"], **extra)


def test_root_dashboard_in_one_call(w):
    with context.agency_context(w["agency"].id):
        g = OfficeGroup.objects.create(name="Mixed")
        for o in (w["div"], w["unit"]):
            OfficeGroupMember.objects.create(group=g, office=o)
    d = dash(client(w, "boss"), w, "root").json()
    assert d["label"] == "PROVISIONAL" and d["has_result"] and d["views"] == ["owner"]
    assert round(float(d["headline"]["cum_actual"]), 6) == 0.315 and d["headline"]["status"] == "DELAYED"
    assert len(d["months"]) == 12 and len(d["series"]["cum_plan"]) == 12
    assert d["series"]["cum_actual"][2:] == [None] * 10  # stops at February
    assert [c["office"]["code"] for c in d["children"]] == ["DIV", "OTHER"]
    assert d["children"][1]["result"] is None  # OTHER has no approved plan
    kinds = [(r["set"]["kind"], r["set"]["name"]) for r in d["rankings"]]
    assert kinds == [("children", "Offices under ROOT"), ("group", "Mixed")]
    children = d["rankings"][0]["rows"]
    assert [(r["office"]["code"], r["rank"]) for r in children] == [("DIV", 1), ("OTHER", None)]
    group = {r["office"]["code"]: r for r in d["rankings"][1]["rows"]}
    assert group["UNIT"]["rank"] == 1 and group["DIV"]["rank"] == 2  # UNIT ranked by its implementing view


def test_implementing_view_and_scope(w):
    unit = client(w, "unit")
    d = dash(unit, w, "unit", view="implementing").json()
    assert d["view"] == "implementing" and d["views"] == ["implementing"]
    assert round(float(d["headline"]["cum_actual"]), 6) == 0.4  # A alone: 4 of 10
    viewer = client(w, "viewer")
    v = dash(viewer, w, "div").json()
    assert v["office"]["ancestors"] == []  # the root is outside a division viewer's scope
    assert [c["office"]["code"] for c in v["children"]] == ["UNIT"]
    assert dash(viewer, w, "root").status_code == 404
    assert dash(viewer, w, "other").status_code == 404
    assert viewer.get("/api/v1/dashboard", office=str(w["div"].id), period="nope").status_code == 404


def test_locked_month_is_final(w):
    boss = client(w, "boss")
    boss.post(f"/api/v1/periods/{w['periods'][1]['id']}/lock")
    d = dash(boss, w, "div", m=1).json()
    assert d["final"] is True and d["label"] == "FINAL"
    assert round(float(d["headline"]["cum_actual"]), 6) == 0.12 and d["headline"]["final"] is True
