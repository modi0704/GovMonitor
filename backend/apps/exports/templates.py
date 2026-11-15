"""Export templates (P10.2): the agency's settings over the system default over built-in values."""

import re
import uuid

from django.core.files.storage import default_storage
from django.utils import timezone

from apps.exports.models import ExportTemplate
from apps.exports.pptx_layout import DEFAULT_SETTINGS as PPTX_DEFAULTS
from apps.reporting import files
from apps.tenancy import context

BUILT_IN = {"pptx": PPTX_DEFAULTS, "xlsx": {"header_fill": "FFD965"}}
EDITABLE = {
    "pptx": {"report_title": 120, "primary_color": 6, "accent_color": 6, "footer_text": 200},
    "xlsx": {"header_fill": 6},
}
COLOR = re.compile(r"^#?[0-9A-Fa-f]{6}$")
LOGO_TYPES = ("png", "jpg", "jpeg")
MAX_LOGO_BYTES = 2 * 1024 * 1024


class TemplateError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def agency_template(kind: str) -> ExportTemplate | None:
    return ExportTemplate.objects.filter(agency__isnull=False, kind=kind, is_default=True).first()


def system_template(kind: str) -> ExportTemplate | None:
    return ExportTemplate.objects.filter(agency__isnull=True, kind=kind, is_default=True).first()


def effective(kind: str) -> dict:
    """The settings an export uses now: built-in < system default < agency template."""
    settings = dict(BUILT_IN[kind])
    for t in (system_template(kind), agency_template(kind)):
        if t is not None:
            settings.update({k: v for k, v in t.settings.items() if v is not None})
    return settings


def _own(kind: str) -> ExportTemplate:
    """The agency's template, created from the system default on first change."""
    t = agency_template(kind)
    if t is None:
        base = system_template(kind)
        t = ExportTemplate(
            agency_id=context.require_agency_id(),
            kind=kind,
            name="Agency template",
            is_default=True,
            settings=dict(base.settings) if base else {},
        )
    return t


def update(kind: str, changes: dict) -> ExportTemplate:
    allowed = EDITABLE[kind]
    clean = {}
    for key, value in changes.items():
        if key not in allowed:
            continue
        text = str(value or "").strip()
        if key.endswith("_color") or key == "header_fill":
            if not COLOR.match(text):
                raise TemplateError(key, "Use a colour such as #1F4E79.")
            text = text.lstrip("#").upper()
        elif key == "report_title" and not text:
            raise TemplateError(key, "The report needs a title.")
        if len(text) > allowed[key]:
            raise TemplateError(key, f"At most {allowed[key]} characters.")
        clean[key] = text
    t = _own(kind)
    t.settings = {**t.settings, **clean}
    t.save()
    return t


def reset(kind: str) -> None:
    t = agency_template(kind)
    if t is not None:
        if t.settings.get("logo_key"):
            default_storage.delete(t.settings["logo_key"])
        t.delete()


def set_logo(kind: str, upload) -> ExportTemplate:
    ext, _ = files.validate(upload)
    if ext not in LOGO_TYPES:
        raise TemplateError("file", "The logo must be a PNG or JPG image.")
    if upload.size > MAX_LOGO_BYTES:
        raise TemplateError("file", "The logo can be at most 2 MB.")
    t = _own(kind)
    old = t.settings.get("logo_key")
    key = f"{context.require_agency_id()}/logos/{timezone.now():%Y}/{uuid.uuid4().hex}.{ext}"
    t.settings = {**t.settings, "logo_key": default_storage.save(key, upload), "logo_type": ext}
    t.save()
    if old:
        default_storage.delete(old)
    return t


def clear_logo(kind: str) -> ExportTemplate | None:
    t = agency_template(kind)
    if t is None or not t.settings.get("logo_key"):
        return t
    default_storage.delete(t.settings["logo_key"])
    t.settings = {k: v for k, v in t.settings.items() if k not in ("logo_key", "logo_type")}
    t.save()
    return t


def logo_bytes(settings: dict) -> bytes | None:
    key = settings.get("logo_key")
    if not key:
        return None
    try:
        with default_storage.open(key, "rb") as fh:
            return fh.read()
    except (FileNotFoundError, OSError):
        return None


def payload(kind: str) -> dict:
    s = effective(kind)
    t = agency_template(kind)
    return {
        "kind": kind,
        "settings": {k: s.get(k, "") for k in EDITABLE[kind]},
        "customised": t is not None,
        "logo_url": f"/api/v1/export-templates/{kind}/logo" if s.get("logo_key") else None,
        "updated_at": t.updated_at.isoformat() if t else None,
    }
