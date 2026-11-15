import io
import zipfile

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog
from apps.reporting.models import Attachment
from apps.tenancy import context
from tests.reporting_helpers import PNG, client, pdf, reporting_world, upload

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
    return tmp_path


@pytest.fixture
def w():
    return reporting_world()


def ooxml(folder):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr(f"{folder}document.xml", "<x/>")
    return buf.getvalue()


def test_upload_list_download_and_soft_delete(w, tmp_storage):
    div = client(w, "div")
    r = upload(div, w)
    assert r.status_code == 201, r.content
    a = r.json()
    assert a["content_type"] == "application/pdf" and len(a["sha256"]) == 64
    with context.agency_context(w["agency"].id):
        stored = Attachment.objects.get(pk=a["id"])
    assert stored.storage_key.startswith(f"{w['agency'].id}/mov/") and stored.storage_key.endswith(
        "-proof.pdf"
    )
    assert default_storage.exists(stored.storage_key)

    listing = div.get(
        "/api/v1/attachments",
        target_type="activity_actual",
        lineage_id=w["acts"]["B"]["lineage_id"],
        period_id=w["periods"][1]["id"],
    ).json()
    assert [x["id"] for x in listing] == [a["id"]]
    viewer = client(w, "viewer")
    d = viewer.get(a["download_url"])
    assert d.status_code == 200 and b"".join(d.streaming_content).startswith(b"%PDF")
    assert d["Content-Disposition"].startswith("attachment")
    assert upload(viewer, w).status_code == 403  # read-only users download, never upload

    assert div.delete(f"/api/v1/attachments/{a['id']}").status_code == 204
    assert viewer.get(a["download_url"]).status_code == 404
    assert default_storage.exists(stored.storage_key)  # soft delete keeps the file
    with context.agency_context(w["agency"].id):
        actions = set(AuditLog.objects.filter(entity_type="attachment").values_list("action", flat=True))
    assert {"upload", "download", "delete"} <= actions


@pytest.mark.parametrize(
    "name,content,code",
    [
        ("virus.exe", b"MZ\x90\x00", "file_type"),
        ("notes.txt", b"hello", "file_type"),
        ("fake.pdf", b"MZ\x90\x00 not a pdf", "file_content"),
        ("fake.png", b"%PDF-1.4", "file_content"),
        ("fake.docx", ooxml("xl/"), "file_content"),
        ("empty.pdf", b"", "file_empty"),
    ],
)
def test_wrong_types_are_refused(w, name, content, code):
    r = upload(client(w, "div"), w, file=SimpleUploadedFile(name, content))
    assert r.status_code == 400 and r.json()["code"] == code


def test_allowed_types(w):
    div = client(w, "div")
    for name, content in [
        ("a.png", PNG),
        ("b.JPG", b"\xff\xd8\xff\xe0" + b"0" * 20),
        ("c.docx", ooxml("word/")),
        ("d.xlsx", ooxml("xl/")),
        ("e.pptx", ooxml("ppt/")),
    ]:
        assert upload(div, w, file=SimpleUploadedFile(name, content)).status_code == 201, name


def test_oversize_is_refused(w, settings):
    settings.MAX_UPLOAD_MB = 1
    big = pdf(content=b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 1))
    r = upload(client(w, "div"), w, file=big)
    assert r.status_code == 400 and r.json()["code"] == "file_too_large"


def test_cross_agency_and_out_of_scope_download_is_404(w):
    a = upload(client(w, "div"), w).json()
    beta = reporting_world("beta")
    assert client(beta, "boss").get(a["download_url"]).status_code == 404
    assert client(w, "other").get(a["download_url"]).status_code == 404


def test_field_unit_attaches_to_its_implementing_activity_only(w):
    unit = client(w, "unit")
    assert upload(unit, w, act="A").status_code == 201
    assert upload(unit, w, act="B").status_code == 404
