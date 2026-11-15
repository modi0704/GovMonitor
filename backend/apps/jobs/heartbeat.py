"""Worker heartbeat, kept in file storage so it works for local and S3 storage alike.

Health checks (`/api/v1/health`) read its age. Stored at ``_system/worker-heartbeat.json``, which is
outside every agency's ``<agency_id>/`` prefix.
"""

import json
from datetime import UTC, datetime

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

HEARTBEAT_KEY = "_system/worker-heartbeat.json"


def beat(now: datetime | None = None, **extra) -> datetime:
    now = now or datetime.now(UTC)
    payload = json.dumps({"at": now.isoformat(), **extra}).encode()
    if default_storage.exists(HEARTBEAT_KEY):
        default_storage.delete(HEARTBEAT_KEY)
    default_storage.save(HEARTBEAT_KEY, ContentFile(payload))
    return now


def last_beat() -> datetime | None:
    try:
        with default_storage.open(HEARTBEAT_KEY, "rb") as fh:
            return datetime.fromisoformat(json.loads(fh.read())["at"])
    except (FileNotFoundError, OSError, KeyError, ValueError):
        return None


def age_seconds(now: datetime | None = None) -> float | None:
    last = last_beat()
    if last is None:
        return None
    return ((now or datetime.now(UTC)) - last).total_seconds()
