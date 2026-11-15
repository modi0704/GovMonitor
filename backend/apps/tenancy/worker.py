"""Helper for background work: run a function inside one agency's context (P1.3, used by P7.7)."""

from collections.abc import Callable
from typing import Any

from apps.tenancy.context import agency_context


def run_in_agency(agency_id, fn: Callable[..., Any], *args, **kwargs) -> Any:
    """Run ``fn`` in its own transaction with ``app.agency_id`` set to ``agency_id``."""
    with agency_context(agency_id):
        return fn(*args, **kwargs)
