"""Phase 6 exit check (MASTERPLAN): a field-unit admin reports on an activity owned by a division;
both the division's owner view and the field unit's implementing view change; a read-only user
gets 403 on save; files are stored under the agency's folder."""

import pytest
from django.core.files.storage import default_storage

from apps.reporting.models import Attachment
from apps.tenancy import context
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
    return tmp_path


def test_field_unit_reports_for_the_division(tmp_storage):
    w = reporting_world()
    div, unit, viewer = client(w, "div"), client(w, "unit"), client(w, "viewer")
    jan = w["periods"][1]["id"]
    owner_q = {"office": str(w["div"].id), "period": jan}
    impl_q = {"office": str(w["unit"].id), "period": jan, "view": "implementing"}

    before_owner = div.get("/api/v1/reports", **owner_q).json()["result"]
    before_impl = unit.get("/api/v1/reports", **impl_q).json()["result"]
    assert before_owner["cum_actual"] == "0" and before_impl["cum_actual"] == "0"

    lineage = w["acts"]["A"]["lineage_id"]
    r = unit.post("/api/v1/reports/save", {**impl_q, "activities": [{"lineage_id": lineage, "actual": "2"}]})
    assert r.status_code == 200, r.content

    after_owner = div.get("/api/v1/reports", **owner_q).json()["result"]
    after_impl = unit.get("/api/v1/reports", **impl_q).json()["result"]
    # Owner view (division): A weighs 0.6 and 2 of 10 is done -> 0.12.
    # Implementing view (unit): A alone -> 0.2.
    assert round(float(after_owner["cum_actual"]), 6) == 0.12
    assert round(float(after_impl["cum_actual"]), 6) == 0.2

    # Read-only user of the division: 403 on save.
    r = viewer.post(
        "/api/v1/reports/save", {**owner_q, "activities": [{"lineage_id": lineage, "actual": "5"}]}
    )
    assert r.status_code == 403

    # Files are stored under the agency's folder.
    a = upload(unit, w, act="A").json()
    with context.agency_context(w["agency"].id):
        key = Attachment.objects.get(pk=a["id"]).storage_key
    assert key.startswith(f"{w['agency'].id}/mov/")
    assert default_storage.exists(key)
    assert (tmp_storage / str(w["agency"].id) / "mov").is_dir()
