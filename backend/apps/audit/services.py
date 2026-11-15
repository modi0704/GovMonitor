"""Recording audit events (MASTERPLAN 6.5, P3.2).

- ``record(action, entity, before, after)``: write one row. Actor, agency, IP, user agent and
  request id come from the current request (``AuditContextMiddleware``) or default to "system".
- ``AuditedModel``: model mixin that records create / update / delete with field-level
  before/after. Password and secret fields are never recorded.
- Bulk queryset operations (``.update()``) bypass model saves; callers record those explicitly.
"""

import contextvars
import datetime
import decimal
import uuid
from contextlib import contextmanager

from django.db import models

from apps.tenancy import context as tenant_context

SENSITIVE_FIELD_PARTS = ("password", "secret", "token", "recovery_codes")

_request: contextvars.ContextVar = contextvars.ContextVar("audit_request", default=None)
_actor_override: contextvars.ContextVar = contextvars.ContextVar("audit_actor", default=None)
_suppressed: contextvars.ContextVar[bool] = contextvars.ContextVar("audit_suppressed", default=False)


def set_request(request) -> contextvars.Token:
    return _request.set(request)


def reset_request(token) -> None:
    _request.reset(token)


@contextmanager
def acting_as(actor_type: str, actor_id=None, label: str = ""):
    """Attribute events in this block to a given actor (platform admin, system job…)."""
    token = _actor_override.set((actor_type, actor_id, label))
    try:
        yield
    finally:
        _actor_override.reset(token)


@contextmanager
def suppressed():
    """Do not record model-level changes in this block (used where an explicit, more meaningful
    event is recorded instead)."""
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)


def is_sensitive(field_name: str) -> bool:
    name = field_name.lower()
    return any(part in name for part in SENSITIVE_FIELD_PARTS)


def jsonable(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [jsonable(v) for v in value]
    return value


def snapshot(instance: models.Model, exclude: set[str] | frozenset = frozenset()) -> dict:
    out = {}
    deferred = instance.get_deferred_fields()  # never trigger a reload from inside a snapshot
    for field in instance._meta.concrete_fields:
        name = field.attname
        if name in exclude or name in deferred or is_sensitive(name) or name == "agency_id":
            continue
        out[name] = jsonable(getattr(instance, name))
    return out


def _actor(request):
    override = _actor_override.get()
    if override:
        return override
    if request is not None:
        platform_admin = getattr(request, "audit_platform_admin", None)
        if platform_admin is not None:
            return ("platform_admin", platform_admin.id, platform_admin.email)
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False) and hasattr(user, "agency_id"):
            return ("user", user.id, user.email)
    return ("system", None, "")


def client_ip(request) -> str | None:
    from django.conf import settings

    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record(
    action: str,
    entity=None,
    *,
    entity_type: str | None = None,
    entity_id=None,
    before: dict | None = None,
    after: dict | None = None,
    office_id=None,
    agency_id=None,
    using: str = "default",
):
    """Write one audit row and return it."""
    from apps.audit.models import AuditLog

    request = _request.get()
    actor_type, actor_id, label = _actor(request)
    if entity is not None:
        entity_type = entity_type or entity._meta.db_table
        entity_id = entity_id or entity.pk
        if office_id is None:
            office_id = audit_office_id(entity)
        if agency_id is None:
            agency_id = getattr(entity, "agency_id", None)
            if entity._meta.db_table == "agency":
                agency_id = entity.pk
    if agency_id is None:
        agency_id = tenant_context.current_agency_id()
    row = AuditLog(
        agency_id=agency_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_label=label or "",
        action=action,
        entity_type=entity_type or "",
        entity_id=str(entity_id) if entity_id is not None else "",
        office_id=office_id,
        before=jsonable(before) if before is not None else None,
        after=jsonable(after) if after is not None else None,
    )
    if request is not None:
        row.ip = client_ip(request)
        row.user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:400]
        row.request_id = getattr(request, "request_id", "")
        request.audit_rows = getattr(request, "audit_rows", 0) + 1
    row.save(using=using)
    return row


def audit_office_id(instance):
    """The office an object belongs to: ``audit_office`` hook, ``office_id``, or the office itself."""
    hook = getattr(instance, "audit_office_id", None)
    if hook is not None and not callable(hook):
        return hook
    if instance._meta.db_table == "office":
        return instance.pk
    return getattr(instance, "office_id", None)


def _action_name(instance, kind: str) -> str:
    return instance.audit_actions.get(kind, kind)


class AuditedModel(models.Model):
    """Records create / update / delete with field-level before/after (P3.2).

    ``audit_exclude``: fields whose changes alone are not worth an audit row (e.g. counters).
    ``audit_actions``: override the action names, e.g. ``{"create": "role_change"}``.
    """

    audit_exclude: frozenset[str] = frozenset()
    audit_actions: dict[str, str] = {}

    class Meta:
        abstract = True

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._audit_loaded = snapshot(instance)
        return instance

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if _suppressed.get():
            self._audit_loaded = snapshot(self)
            return
        using = kwargs.get("using") or self._state.db or "default"
        now = snapshot(self)
        if creating:
            record(_action_name(self, "create"), self, after=now, using=using)
        else:
            old = getattr(self, "_audit_loaded", None) or {}
            changed = [k for k, v in now.items() if k in old and old[k] != v and k not in self.audit_exclude]
            if changed:
                record(
                    _action_name(self, "update"),
                    self,
                    before={k: old.get(k) for k in changed},
                    after={k: now[k] for k in changed},
                    using=using,
                )
        self._audit_loaded = now

    def delete(self, *args, **kwargs):
        before = snapshot(self)
        pk = self.pk
        using = kwargs.get("using") or self._state.db or "default"
        office_id = audit_office_id(self)
        agency_id = getattr(self, "agency_id", None)
        result = super().delete(*args, **kwargs)
        if not _suppressed.get():
            record(
                _action_name(self, "delete"),
                entity_type=self._meta.db_table,
                entity_id=pk,
                before=before,
                office_id=office_id,
                agency_id=agency_id,
                using=using,
            )
        return result
