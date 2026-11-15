"""P9.8 — export a plan, import the file into a new fiscal year, compare activities and targets."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.jobs import worker
from apps.planning.models import Plan
from apps.tenancy import context
from tests.export_helpers import FIXTURES, build, rdi_world

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not (FIXTURES / "most_fy2023_rdi.json").exists(), reason="P4.2 fixtures missing"),
]

INDICATORS = [
    {"client_key": "i1", "code": "OI-1", "name": "Proposals evaluated", "annual_target": "90",
     "targets": ["0", "30", "30", "0", "30"] + ["0"] * 7, "sort_order": 0},
    {"client_key": "i2", "code": "OI-2", "name": "Agreements signed", "annual_target": "8",
     "targets": ["0", "2", "2", "0", "2", "2"] + ["0"] * 6, "sort_order": 10},
]  # fmt: skip


def snapshot(plan: Plan) -> dict:
    rows = list(plan.rows.select_related("parent").prefetch_related("targets__period").order_by("sort_order"))
    codes = {r.id: r.code or r.title for r in rows}
    activities = [
        {
            "kind": r.row_kind,
            "code": r.code,
            "title": r.title,
            "parent": codes.get(r.parent_id),
            "unit": r.unit,
            "measure": r.measure_type,
            "target": r.annual_target,
            "unit_cost": r.unit_cost,
            "total_cost": r.total_cost,
            "monthly": [
                t.planned_qty
                for t in sorted(r.targets.all(), key=lambda t: t.period.month_index)
                if t.planned_qty
            ],  # fmt: skip
        }
        for r in rows
    ]
    indicators = [
        {"code": i.code, "name": i.name, "target": i.annual_target,
         "monthly": {t.period.month_index: t.planned_value for t in i.targets.all() if t.planned_value}}
        for i in plan.indicators.prefetch_related("targets__period").order_by("sort_order")
    ]  # fmt: skip
    return {"activities": activities, "indicators": indicators}


def test_export_then_import_into_a_new_year_keeps_activities_and_targets():
    w = rdi_world(outline=True, indicators=INDICATORS)
    api = w["api"]
    data, _ = build(w["agency"], w["rdi"], w["periods"][12]["id"])

    fy = api.post("/api/v1/fiscal-years", {"label": "2024", "start_year": 2024}).json()
    upload = SimpleUploadedFile("RDI-2023.xlsx", data.getvalue())
    r = api.c.post(
        "/api/v1/imports/plan", {"file": upload, "office_id": str(w["rdi"].id), "fiscal_year_id": fy["id"]}
    )
    assert r.status_code == 202, r.content
    worker.run_pending()
    job = api.get(f"/api/v1/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job
    assert job["result"]["sheet"] == "RDI"

    with context.agency_context(w["agency"].id):
        old = Plan.objects.get(office=w["rdi"], fiscal_year_id=w["fy"]["id"])
        new = Plan.objects.get(office=w["rdi"], fiscal_year_id=fy["id"])
        assert new.status == "draft"
        before, after = snapshot(old), snapshot(new)
    assert len(after["activities"]) == len(before["activities"]) == 16  # 6 outline rows + 10 activities
    for b, a in zip(before["activities"], after["activities"], strict=True):
        assert a == b, (b["code"], {k: (b[k], a[k]) for k in b if a[k] != b[k]})
    assert after["indicators"] == before["indicators"]
    # Lineages are new: the imported plan is a fresh plan, not a copy of last year's rows.
    with context.agency_context(w["agency"].id):
        assert not set(new.rows.values_list("lineage_id", flat=True)) & set(
            old.rows.values_list("lineage_id", flat=True)
        )
