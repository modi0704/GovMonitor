"""P9.1: export jobs — create, poll, download; "My exports"; who may see a job."""

import io

import openpyxl
import pytest

from apps.audit.models import AuditLog
from apps.jobs import worker
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def request_export(c, w, **extra):
    body = {"scope": "office", "office_id": str(w["div"].id), "period_id": w["periods"][3]["id"]}
    return c.post("/api/v1/exports/xlsx", {**body, **extra})


def test_export_job_lifecycle_and_download():
    w = reporting_world()
    div = client(w, "div")
    r = request_export(div, w)
    assert r.status_code == 202, r.content
    job = r.json()
    assert job["status"] == "queued" and job["kind"] == "export_xlsx" and job["download_url"] is None
    assert job["params"]["scope"] == "office" and job["params"]["view"] == "owner"

    assert worker.run_pending() == 1
    job = div.get(f"/api/v1/jobs/{job['id']}").json()
    assert job["status"] == "done", job
    assert job["file_name"].endswith(".xlsx") and job["download_url"]

    mine = div.get("/api/v1/jobs").json()
    assert [j["id"] for j in mine] == [job["id"]]
    assert client(w, "other").get("/api/v1/jobs").json() == []

    r = div.c.get(job["download_url"])
    assert r.status_code == 200
    assert r["Content-Disposition"].startswith("attachment")
    wb = openpyxl.load_workbook(io.BytesIO(b"".join(r.streaming_content)))
    assert wb.sheetnames[0] == "SUMMARY"

    with context.agency_context(w["agency"].id):
        actions = list(AuditLog.objects.filter(entity_type="job").values_list("action", flat=True))
    assert actions.count("export") == 1 and actions.count("download") == 1
    assert "create" not in actions


def test_jobs_are_private_to_the_requester_and_agency_admins():
    w = reporting_world()
    job = request_export(client(w, "div"), w).json()
    worker.run_pending()
    assert client(w, "other").get(f"/api/v1/jobs/{job['id']}").status_code == 404
    assert client(w, "other").get(f"/api/v1/jobs/{job['id']}/download").status_code == 404
    assert w["boss"].get(f"/api/v1/jobs/{job['id']}").status_code == 200  # agency admin


def test_export_scope_is_checked():
    w = reporting_world()
    other = client(w, "other")
    assert request_export(other, w).status_code == 404  # DIV is outside OTHER's scope
    assert request_export(other, w, scope="agency").status_code == 404  # root not visible
    assert request_export(w["boss"], w, scope="agency").status_code == 202
    assert request_export(w["boss"], w, scope="everything").status_code == 400
    assert request_export(w["boss"], w, view="sideways").status_code == 400
    assert request_export(w["boss"], w, period_id=None).status_code == 400


def test_download_before_done_is_404_and_failures_show_one_line(monkeypatch):
    w = reporting_world()
    div = client(w, "div")
    job = request_export(div, w).json()
    assert div.get(f"/api/v1/jobs/{job['id']}/download").status_code == 404

    def boom(_job):
        raise ValueError("disk full")

    monkeypatch.setitem(worker.HANDLERS, "export_xlsx", boom)
    worker.run_pending()
    job = div.get(f"/api/v1/jobs/{job['id']}").json()
    assert job["status"] == "failed" and job["error"] == "ValueError: disk full"
