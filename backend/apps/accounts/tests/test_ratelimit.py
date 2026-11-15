"""P14.1: rate limits on sign-in (per network address) and on exports and imports (per user)."""

import pytest
from django.test import Client

from apps.accounts import ratelimit
from apps.jobs.models import Job
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db(databases=["default", "owner"])


def attempt(c, email, password, ip):
    return c.post(
        "/api/v1/auth/login", {"email": email, "password": password}, content_type="application/json",
        REMOTE_ADDR=ip,
    )  # fmt: skip


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_many_failed_sign_ins_from_one_address_are_slowed_down(settings):
    """Committed like real requests (unknown-email failures are written by the owner connection)."""
    settings.SIGNIN_FAILURES_PER_IP = 4
    w = reporting_world()
    c = Client()
    c.get("/api/v1/auth/csrf")
    for i in range(4):  # unknown emails and wrong passwords both count
        email = f"nobody{i}@alpha.gov" if i % 2 else "div@alpha.gov"
        assert attempt(c, email, "wrong-password-123", "203.0.113.9").status_code == 400
    r = attempt(c, "boss@alpha.gov", "correct-or-not", "203.0.113.9")
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"
    # Another address is not affected.
    from tests.factories import DEFAULT_PASSWORD

    assert attempt(Client(), "boss@alpha.gov", DEFAULT_PASSWORD, "198.51.100.7").status_code == 200
    assert w["agency"]


def test_exports_are_limited_per_user():
    w = reporting_world()
    div = client(w, "div")
    body = {"scope": "office", "office_id": str(w["div"].id), "period_id": w["periods"][1]["id"]}
    for _ in range(ratelimit.JOBS_PENDING_PER_USER):
        assert div.post("/api/v1/exports/xlsx", body).status_code == 202
    r = div.post("/api/v1/exports/pptx", body)
    assert r.status_code == 429 and "being prepared" in r.json()["detail"]
    # Another user still can.
    assert w["boss"].post("/api/v1/exports/xlsx", body).status_code == 202
    # Once the waiting ones are done, the hourly ceiling still applies.
    with context.agency_context(w["agency"].id):
        Job.objects.update(status="done")
        user = Job.objects.filter(requested_by__email="div@alpha.gov").first().requested_by
        Job.objects.bulk_create(
            [
                Job(kind="export_xlsx", status="done", requested_by=user)
                for _ in range(ratelimit.JOBS_PER_USER_PER_HOUR)
            ]
        )
    r = div.post("/api/v1/exports/xlsx", body)
    assert r.status_code == 429 and "an hour" in r.json()["detail"]
