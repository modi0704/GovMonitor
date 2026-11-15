"""P11.1: the agency's alert rule."""

import pytest

from apps.alerts.models import AlertRule
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def test_defaults_until_changed_then_saved_once_per_agency(settings):
    settings.EMAIL_ENABLED = False
    w = reporting_world()
    boss = w["boss"]
    assert boss.get("/api/v1/alert-rules").json() == {
        "remind_days_before": [5, 1],
        "delay_threshold": "0.05",
        "email_enabled": False,
        "email_available": False,
    }
    r = boss.patch("/api/v1/alert-rules", {"remind_days_before": "1, 7,3", "delay_threshold": "0.1"})
    assert r.status_code == 200, r.content
    assert r.json()["remind_days_before"] == [7, 3, 1] and r.json()["delay_threshold"] == "0.1"
    boss.patch("/api/v1/alert-rules", {"email_enabled": True})
    with context.agency_context(w["agency"].id):
        assert AlertRule.objects.count() == 1
        assert AlertRule.objects.get().email_enabled is True


def test_invalid_values_and_permissions():
    w = reporting_world()
    boss = w["boss"]
    assert boss.patch("/api/v1/alert-rules", {"remind_days_before": "soon"}).status_code == 400
    assert boss.patch("/api/v1/alert-rules", {"remind_days_before": [40]}).status_code == 400
    assert boss.patch("/api/v1/alert-rules", {"delay_threshold": "2"}).status_code == 400
    assert client(w, "div").get("/api/v1/alert-rules").status_code == 403
