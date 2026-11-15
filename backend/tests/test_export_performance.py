"""Phase 9 exit check: a 500-activity office exports in under 30 seconds (through the job)."""

import io
import random
import time
import uuid
from decimal import Decimal

import openpyxl
import pytest

from apps.jobs import worker
from apps.jobs.models import Job
from apps.planning.models import Activity, ActivityTarget, Plan
from apps.planning.services import create_fiscal_year, set_fiscal_year_status
from apps.reporting.models import ActivityActual
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = [pytest.mark.django_db, pytest.mark.perf]
ACTIVITIES = 500
LIMIT_SECONDS = 30


@pytest.fixture(autouse=True)
def tmp_storage(tmp_path, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }


def big_office():
    rng = random.Random(9)
    agency = make_agency("big")
    root = make_root(agency)
    office = make_office(root, "BIG")
    assign(make_user(agency, "boss@big.gov"), root, "admin")
    with context.agency_context(agency.id):
        fy = create_fiscal_year("BIG", 2026)
        set_fiscal_year_status(fy, "open")
        periods = {p.month_index: p for p in fy.periods.all()}
        plan = Plan.objects.create(office=office, fiscal_year=fy, status="approved", version=1)
        outline = [
            Activity(
                plan=plan,
                lineage_id=uuid.uuid4(),
                row_kind="output",
                code=f"O{k}.",
                title=f"Output {k}",
                sort_order=k * 1000,
            )  # fmt: skip
            for k in range(10)
        ]
        Activity.objects.bulk_create(outline)
        acts, targets, actuals = [], [], []
        for i in range(ACTIVITIES):
            target = Decimal(rng.randint(1, 24))
            act = Activity(
                plan=plan, lineage_id=uuid.uuid4(), parent=outline[i // 50], row_kind="activity",
                code=f"BIG-{i}", title=f"Activity {i} " + "x" * 60, sort_order=(i // 50) * 1000 + i + 1,
                measure_type="recurring" if i % 25 == 0 else "quantity", unit="unit", annual_target=target,
                total_cost=Decimal(rng.randint(1000, 900000)), implementing_office=office,
            )  # fmt: skip
            acts.append(act)
            for m in range(1, 13):
                targets.append(ActivityTarget(activity=act, period=periods[m], planned_qty=target / 12))
            for m in range(1, 7):
                actuals.append(
                    ActivityActual(activity_lineage_id=act.lineage_id, period=periods[m], office=office,
                                   actual_qty=Decimal(rng.randint(0, 3)))
                )  # fmt: skip
        Activity.objects.bulk_create(acts)
        ActivityTarget.objects.bulk_create(targets, batch_size=5000)
        ActivityActual.objects.bulk_create(actuals, batch_size=5000)
    return agency, office, periods


def test_500_activity_office_exports_in_under_30_seconds():
    agency, office, periods = big_office()
    api = Json(api_client("boss@big.gov"))
    r = api.post(
        "/api/v1/exports/xlsx",
        {"scope": "office", "office_id": str(office.id), "period_id": str(periods[6].id)},
    )
    assert r.status_code == 202, r.content
    started = time.perf_counter()
    assert worker.run_pending() == 1
    elapsed = time.perf_counter() - started
    with context.agency_context(agency.id):
        job = Job.objects.get()
    assert job.status == "done", job.error
    assert elapsed < LIMIT_SECONDS, f"export took {elapsed:.1f}s"
    download = api.c.get(f"/api/v1/jobs/{job.id}/download")
    ws = openpyxl.load_workbook(io.BytesIO(b"".join(download.streaming_content)), read_only=True)["BIG"]
    assert ws.max_row > 8 + 10 + 2 * ACTIVITIES
    print(f"500-activity export: {elapsed:.2f}s")
