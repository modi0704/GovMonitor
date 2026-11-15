"""Upload rules and storage for supporting files (MASTERPLAN 6.6, D15, P6.2).

Allowed: PDF, JPG, PNG, DOCX, XLSX, PPTX — the extension AND the sniffed content must agree.
Maximum MAX_UPLOAD_MB. Stored under ``<agency_id>/mov/<yyyy>/<uuid>-<safe name>``; never served
from storage directly, only through the authorised download endpoint.
"""

import hashlib
import re
import uuid
import zipfile

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.exports import hooks

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
OOXML_FOLDER = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}


class UploadError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def extension(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def sniff(ext: str, file) -> bool:
    """Does the file's content match its extension?"""
    file.seek(0)
    head = file.read(16)
    file.seek(0)
    if ext == "pdf":
        return head.startswith(b"%PDF-")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in OOXML_FOLDER:
        if not head.startswith(b"PK\x03\x04"):
            return False
        try:
            with zipfile.ZipFile(file) as zf:
                names = zf.namelist()
        except zipfile.BadZipFile:
            return False
        finally:
            file.seek(0)
        return "[Content_Types].xml" in names and any(n.startswith(OOXML_FOLDER[ext]) for n in names)
    return False


def safe_name(name: str) -> str:
    base, _, ext = name.rpartition(".")
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base or name).strip("-.")[:80] or "file"
    return f"{base}.{ext.lower()}" if ext else base


def validate(upload) -> tuple[str, str]:
    ext = extension(upload.name or "")
    if ext not in CONTENT_TYPES:
        raise UploadError("file_type", "Only PDF, JPG, PNG, DOCX, XLSX and PPTX files can be attached.")
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    if upload.size > limit:
        raise UploadError("file_too_large", f"Files can be at most {settings.MAX_UPLOAD_MB} MB.")
    if upload.size == 0:
        raise UploadError("file_empty", "The file is empty.")
    if not sniff(ext, upload):
        raise UploadError("file_content", f"The file's content is not a valid .{ext} file.")
    return ext, CONTENT_TYPES[ext]


def sha256_of(upload) -> str:
    digest = hashlib.sha256()
    upload.seek(0)
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def store(upload, agency_id) -> dict:
    """Validate, scan and store. Returns the attachment fields to save."""
    ext, content_type = validate(upload)
    try:
        hooks.scan_upload(upload)
    except hooks.UploadRejected as exc:
        raise UploadError("file_rejected", str(exc) or "The file was rejected by the scanner.") from exc
    digest = sha256_of(upload)
    name = safe_name(upload.name)
    key = f"{agency_id}/mov/{timezone.now():%Y}/{uuid.uuid4().hex}-{name}"
    saved_key = default_storage.save(key, upload)
    return {
        "file_name": (upload.name or name)[:255],
        "content_type": content_type,
        "size_bytes": upload.size,
        "sha256": digest,
        "storage_key": saved_key,
    }
