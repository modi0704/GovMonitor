"""P11.3: the notification centre API — own notifications only, unread count, mark read."""

import uuid

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.alerts.models import Notification
from apps.audit.models import AuditLog
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def make(w, who, n, read=False) -> list:
    with context.agency_context(w["agency"].id):
        user = User.objects.get(email=f"{who}@{w['code']}.gov")
        return [
            Notification.objects.create(
                user=user,
                type="cutoff_reminder",
                title=f"{who} {i}",
                link="/reports",
                dedupe_key=str(uuid.uuid4()),
                read_at=timezone.now() if read else None,
            ).id
            for i in range(n)
        ]


@pytest.fixture
def w():
    world = reporting_world()
    with context.agency_context(world["agency"].id):
        Notification.objects.all().delete()
    return world


def test_list_count_and_mark_read(w):
    ids = make(w, "div", 3)
    make(w, "div", 1, read=True)
    make(w, "other", 2)
    div = client(w, "div")
    data = div.get("/api/v1/notifications").json()
    assert data["unread"] == 3
    assert sorted(r["title"] for r in data["results"]) == ["div 0", "div 0", "div 1", "div 2"]
    assert len(div.get("/api/v1/notifications?unread=1").json()["results"]) == 3
    assert div.get("/api/v1/notifications/unread-count").json() == {"unread": 3}

    with context.agency_context(w["agency"].id):
        audit_before = AuditLog.objects.count()
    assert div.post(f"/api/v1/notifications/{ids[0]}/read").json() == {"unread": 2}
    assert div.post(f"/api/v1/notifications/{ids[0]}/read").json() == {"unread": 2}  # idempotent
    assert div.post("/api/v1/notifications/read-all").json() == {"unread": 0}
    with context.agency_context(w["agency"].id):
        assert AuditLog.objects.count() == audit_before  # reading one's inbox is not audited
    assert client(w, "other").get("/api/v1/notifications/unread-count").json() == {"unread": 2}


def test_someone_elses_notification_is_404(w):
    [theirs] = make(w, "other", 1)
    assert client(w, "div").post(f"/api/v1/notifications/{theirs}/read").status_code == 404
    assert client(w, "other").get("/api/v1/notifications/unread-count").json() == {"unread": 1}
