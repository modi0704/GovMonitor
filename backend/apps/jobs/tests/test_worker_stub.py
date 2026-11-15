from datetime import UTC, datetime, timedelta

from django.core.management import call_command

from apps.jobs import heartbeat


def test_run_worker_once_records_heartbeat(tmp_path, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }
    assert heartbeat.age_seconds() is None
    call_command("run_worker", "--once")
    age = heartbeat.age_seconds()
    assert age is not None and 0 <= age < 5
    later = datetime.now(UTC) + timedelta(seconds=100)
    assert heartbeat.age_seconds(now=later) > 99
