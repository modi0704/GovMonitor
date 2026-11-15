"""Where job output files live: ``<agency_id>/exports/<yyyy>/<job id>-<name>`` (MASTERPLAN 6.6).

Files are never served from storage directly, only through ``GET /api/v1/jobs/{id}/download``.
"""

import io

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.reporting.files import safe_name

CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def store_result(job, name: str, data: bytes | io.BytesIO) -> str:
    """Save a job's output file and record its key on the job (in the same transaction)."""
    if isinstance(data, io.BytesIO):
        data = data.getvalue()
    key = f"{job.agency_id}/exports/{timezone.now():%Y}/{job.pk}-{safe_name(name)}"
    saved = default_storage.save(key, ContentFile(data))
    job.result_key = saved
    job.save(update_fields=["result_key"])
    return saved


def content_type(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return CONTENT_TYPES.get(ext, "application/octet-stream")
