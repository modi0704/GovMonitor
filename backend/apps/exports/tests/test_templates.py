"""P10.2: export templates — system default, agency settings, logo; admin only."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.exports import templates
from apps.exports.models import ExportTemplate
from apps.tenancy import context
from tests.reporting_helpers import PNG, client, pdf, reporting_world

pytestmark = pytest.mark.django_db
URL = "/api/v1/export-templates/pptx"


def test_system_default_until_the_agency_changes_something():
    w = reporting_world()
    boss = w["boss"]
    data = boss.get(URL).json()
    assert data["customised"] is False and data["logo_url"] is None
    assert data["settings"]["report_title"] == "Performance Monitoring Report"
    assert data["settings"]["primary_color"] == "1F4E79"

    r = boss.patch(
        URL, {"report_title": "Quarterly Review", "primary_color": "#0b1f5c", "footer_text": "Internal"}
    )
    assert r.status_code == 200, r.content
    assert r.json()["customised"] is True
    assert r.json()["settings"]["primary_color"] == "0B1F5C"
    with context.agency_context(w["agency"].id):
        assert templates.effective("pptx")["report_title"] == "Quarterly Review"
        assert templates.effective("pptx")["accent_color"] == "F2C14E"  # untouched: system default
        assert ExportTemplate.objects.filter(agency__isnull=True).count() == 2  # system rows unchanged

    assert boss.patch(URL, {"primary_color": "navy"}).status_code == 400
    assert boss.patch(URL, {"report_title": ""}).status_code == 400

    assert boss.delete(URL).json()["customised"] is False
    assert boss.get(URL).json()["settings"]["report_title"] == "Performance Monitoring Report"


def test_logo_upload_preview_and_removal():
    w = reporting_world()
    boss = w["boss"]
    r = boss.c.post(f"{URL}/logo", {"file": SimpleUploadedFile("logo.png", PNG)})
    assert r.status_code == 200, r.content
    assert r.json()["logo_url"] == f"{URL}/logo"
    got = boss.c.get(f"{URL}/logo")
    assert got.status_code == 200 and b"".join(got.streaming_content) == PNG
    assert boss.c.post(f"{URL}/logo", {"file": pdf()}).status_code == 400  # not an image
    assert boss.delete(f"{URL}/logo").json()["logo_url"] is None
    assert boss.c.get(f"{URL}/logo").status_code == 404


def test_only_the_agency_administrator_may_change_templates():
    w = reporting_world()
    div = client(w, "div")  # division admin, not agency admin
    assert div.get(URL).status_code == 403
    assert div.patch(URL, {"report_title": "Mine"}).status_code == 403
    assert w["boss"].get("/api/v1/export-templates/docx").status_code == 404
