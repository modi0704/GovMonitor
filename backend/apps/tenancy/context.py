"""The current agency (tenant) for this unit of work — MASTERPLAN 6.1.

The database setting ``app.agency_id`` is the source of truth: every row-level-security policy
reads it. A context variable mirrors it so model code can fill ``agency_id`` without a query.
``SET LOCAL`` (``set_config(..., true)``) only lasts until the end of the current transaction, so
these helpers must run inside ``transaction.atomic``.
"""

import contextlib
import contextvars
import uuid

from django.db import connections, transaction

_current: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("agency_id", default=None)


class NoAgencyContext(RuntimeError):
    """Raised when tenant data is written with no agency set."""


def _as_uuid(value) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def set_agency(agency_id, using: str = "default") -> None:
    """``SET LOCAL app.agency_id`` on the current transaction (empty string = no agency)."""
    value = _as_uuid(agency_id)
    connection = connections[using]
    if not connection.in_atomic_block:
        raise RuntimeError("set_agency() must run inside transaction.atomic()")
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.agency_id', %s, true)", [str(value) if value else ""])
    _current.set(value)


def current_agency_id() -> uuid.UUID | None:
    return _current.get()


def require_agency_id() -> uuid.UUID:
    value = _current.get()
    if value is None:
        raise NoAgencyContext("No agency is set for this operation")
    return value


def clear() -> None:
    _current.set(None)


@contextlib.contextmanager
def agency_context(agency_id, using: str = "default"):
    """Run a block inside a transaction (or savepoint) with ``app.agency_id`` set.

    Used by the worker (per job), management commands and tests. Restores the previous agency on
    exit, in the database and in the context variable.
    """
    previous = _current.get()
    with transaction.atomic(using=using):
        set_agency(agency_id, using=using)
        try:
            yield
        finally:
            connection = connections[using]
            if connection.in_atomic_block and not connection.needs_rollback:
                set_agency(previous, using=using)
            _current.set(previous)
