import pytest
from django.core.management import call_command


@pytest.fixture
def tmp_storage(tmp_path, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }
    return tmp_path


@pytest.mark.django_db
def test_health_degraded_without_worker(client, tmp_storage):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["database"]["ok"] and body["storage"]["ok"]
    assert body["worker"] == {"ok": False, "heartbeat_age_seconds": None}
    from pathlib import Path

    assert body["version"] == (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
    assert not any(p.name.startswith("health-") for p in (tmp_storage / "_system").glob("*"))


@pytest.mark.django_db
def test_health_ok_with_fresh_heartbeat(client, tmp_storage):
    call_command("run_worker", "--once")
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok" and body["worker"]["ok"]


@pytest.mark.django_db
def test_health_error_when_storage_fails(client, settings, tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(blocked)},
        },
    }
    r = client.get("/api/v1/health")
    assert r.status_code == 503 and r.json()["status"] == "error"


@pytest.mark.django_db
def test_health_rejects_post(client):
    assert client.post("/api/v1/health").status_code in (403, 405)
