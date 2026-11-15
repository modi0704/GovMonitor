"""P9.7: plan import template and the import_plan job (MASTERPLAN 9.4)."""

import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog
from apps.exports.plan_import import split_code
from apps.jobs import worker
from apps.planning.models import Activity, Plan
from apps.tenancy import context
from tests.reporting_helpers import client, pdf, reporting_world

pytestmark = pytest.mark.django_db
MONTHS = "OPQRSTUVWXYZ"


def template(c, w, office="other"):
    r = c.c.get(f"/api/v1/imports/plan-template?fiscal_year_id={w['fy']['id']}&office_id={w[office].id}")
    assert r.status_code == 200, r.content
    return openpyxl.load_workbook(io.BytesIO(b"".join(r.streaming_content)))


def plan_row(ws, r, text, target, cost, monthly, unit="unit"):
    ws[f"H{r}"], ws[f"I{r}"], ws[f"J{r}"], ws[f"L{r}"], ws[f"N{r}"] = text, target, unit, cost, "PLAN"
    for col, v in zip(MONTHS, monthly, strict=False):
        ws[f"{col}{r}"] = v
    ws[f"N{r + 1}"] = "ACTUAL"
    ws[f"O{r + 1}"] = 99  # actuals are ignored


def filled(wb) -> bytes:
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def upload(c, w, data, office="other", name="plan.xlsx"):
    f = SimpleUploadedFile(name, data, content_type="application/octet-stream")
    return c.c.post(
        "/api/v1/imports/plan", {"file": f, "office_id": str(w[office].id), "fiscal_year_id": w["fy"]["id"]}
    )


def good_workbook(c, w):
    wb = template(c, w)
    ws = wb["PLAN"]
    ws["B8"] = "OC1. Better services"
    ws["D9"] = "OP1.1. Trained staff"
    plan_row(ws, 10, "OP1.1-1 Training courses", 4, 400000, [1, 1, 1, 1])
    plan_row(ws, 12, "OP1.1-2 Manuals", 2, 100000, [0, 0, 2])
    ws["G14"] = "PR1 Outreach project"
    plan_row(ws, 15, "Radio spots", 12, 50000, [1] * 12)
    ws["H17"], ws["B17"] = "TOTAL COST", "TOTAL COST"
    ws["H30"] = "OUTPUT INDICATORS"
    ws["H31"], ws["I31"] = "OI1", "People trained"
    ws["O31"], ws["P31"] = 10, 20
    return wb


def test_template_is_the_office_sheet_with_headers_only():
    w = reporting_world()
    wb = template(client(w, "other"), w)
    assert wb.sheetnames == ["PLAN", "INSTRUCTIONS"]
    ws = wb["PLAN"]
    assert ws["A1"].value == "Fiscal Year 2026" and ws["A3"].value == "OTHER" and ws["A4"].value is None
    assert ws["H5"].value == "ACTIVITIES" and ws["N7"].value == "REMARKS" and ws["O7"].value == "JAN"
    assert ws["A8"].value == "OTHER"
    assert ws.max_row == 8


def test_import_creates_a_draft_plan_with_outline_activities_and_indicators():
    w = reporting_world()
    other = client(w, "other")
    r = upload(other, w, filled(good_workbook(other, w)))
    assert r.status_code == 202, r.content
    job = r.json()
    assert job["kind"] == "import_plan"
    assert worker.run_pending() == 1
    job = other.get(f"/api/v1/jobs/{job['id']}").json()
    assert job["status"] == "done", job
    assert job["result"]["activities"] == 3 and job["result"]["indicators"] == 1
    assert job["download_url"] is None
    with context.agency_context(w["agency"].id):
        plan = Plan.objects.get(office=w["other"], fiscal_year_id=w["fy"]["id"])
        assert plan.status == "draft" and str(plan.id) == job["result"]["plan_id"]
        rows = {r.code or r.title: r for r in plan.rows.all()}
        assert rows["OC1."].row_kind == "outcome" and rows["OC1."].title == "Better services"
        assert rows["OP1.1."].parent_id == rows["OC1."].id
        training = rows["OP1.1-1"]
        assert (training.row_kind, training.parent_id, training.annual_target) == (
            "activity",
            rows["OP1.1."].id,
            4,
        )
        assert training.title == "Training courses" and training.unit == "unit"
        assert sorted(t.planned_qty for t in training.targets.all()) == [1, 1, 1, 1]
        assert rows["PR1"].row_kind == "project" and rows["PR1"].parent_id == rows["OP1.1."].id
        assert rows["Radio spots"].parent_id == rows["PR1"].id
        ind = plan.indicators.get()
        assert (ind.code, ind.name, ind.annual_target) == ("OI1", "People trained", 30)
        assert AuditLog.objects.filter(action="import", entity_type="job").count() == 1


def test_any_error_imports_nothing_and_lists_each_row():
    w = reporting_world()
    other = client(w, "other")
    wb = good_workbook(other, w)
    ws = wb["PLAN"]
    ws["I10"] = "four"  # not a number
    ws["Q12"] = 5  # Manuals: monthly targets now add up to 5, not 2
    ws["N20"] = "ACTUAL"  # an ACTUAL row without its PLAN row
    ws["H17"] = ws["B17"] = None
    r = upload(other, w, filled(wb))
    worker.run_pending()
    job = other.get(f"/api/v1/jobs/{r.json()['id']}").json()
    assert job["status"] == "failed" and "nothing was imported" in job["error"]
    by_row = {e["row"]: e for e in job["result"]["errors"]}
    assert "not a number" in by_row[10]["message"] and by_row[10]["column"] == "I"
    assert by_row[20]["message"].startswith("This ACTUAL row")
    with context.agency_context(w["agency"].id):
        assert not Plan.objects.filter(office=w["other"]).exists()

    # Fix the parse problems: the remaining validation error (targets sum) still blocks the import.
    ws["I10"] = 4
    ws["N20"] = None
    r = upload(other, w, filled(wb))
    worker.run_pending()
    job = other.get(f"/api/v1/jobs/{r.json()['id']}").json()
    assert job["status"] == "failed"
    [problem] = job["result"]["errors"]
    assert problem["row"] == 12 and "add up to 5" in problem["message"]
    with context.agency_context(w["agency"].id):
        assert not Plan.objects.filter(office=w["other"]).exists()
        assert not Activity.objects.filter(plan__office=w["other"]).exists()


def test_import_is_refused_up_front_when_it_cannot_work():
    w = reporting_world()
    other, viewer = client(w, "other"), client(w, "viewer")
    data = filled(good_workbook(other, w))
    assert upload(viewer, w, data, office="div").status_code == 404  # read-only: no edit scope
    assert upload(w["boss"], w, data, office="div").status_code == 409  # DIV already has a plan
    r = other.c.post(
        "/api/v1/imports/plan",
        {"file": pdf(), "office_id": str(w["other"].id), "fiscal_year_id": w["fy"]["id"]},
    )
    assert r.status_code == 400
    assert upload(other, w, b"PK\x03\x04 not really a workbook").status_code == 400


def test_split_code():
    assert split_code("RDID1.1.1. Increased access") == ("RDID1.1.1.", "Increased access")
    assert split_code("PME-3 Workshop") == ("PME-3", "Workshop")
    assert split_code("Radio spots") == ("", "Radio spots")
    assert split_code("X1.") == ("", "X1.")
