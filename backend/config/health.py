"""GET /api/v1/health — database reachable, storage writable, worker heartbeat age (P0.7).

HTTP 200 while the database and storage work (``status`` is ``ok`` or, with a stale or missing
worker heartbeat, ``degraded``); HTTP 503 when the database or storage fails. Reveals no data.
"""

import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.jobs import heartbeat


def _check_database() -> bool:
    try:
        with connections["default"].cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() == (1,)
    except Exception:  # noqa: BLE001 — any failure means "not reachable"
        return False


def _check_storage() -> bool:
    key = f"_system/health-{uuid.uuid4().hex}.txt"
    try:
        saved = default_storage.save(key, ContentFile(b"ok"))
        default_storage.delete(saved)
        return True
    except Exception:  # noqa: BLE001
        return False


@never_cache
@require_GET
def health(request):
    db_ok = _check_database()
    storage_ok = _check_storage()
    age = heartbeat.age_seconds()
    worker_ok = age is not None and age <= settings.WORKER_HEARTBEAT_STALE_SECONDS
    if not (db_ok and storage_ok):
        status = "error"
    elif not worker_ok:
        status = "degraded"
    else:
        status = "ok"
    body = {
        "status": status,
        "database": {"ok": db_ok},
        "storage": {"ok": storage_ok},
        "worker": {
            "ok": worker_ok,
            "heartbeat_age_seconds": None if age is None else round(age, 1),
        },
        "deployment_mode": settings.DEPLOYMENT_MODE,
        "version": settings.APP_VERSION,
    }
    return JsonResponse(body, status=200 if status != "error" else 503)
