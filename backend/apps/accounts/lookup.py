"""Pre-authentication lookups through SECURITY DEFINER functions (P1.3)."""

import uuid
from dataclasses import dataclass

from django.db import connection


@dataclass(frozen=True)
class UserLookup:
    id: uuid.UUID
    agency_id: uuid.UUID
    password: str


def lookup_user_by_email(email: str) -> UserLookup | None:
    with connection.cursor() as cur:
        cur.execute("SELECT id, agency_id, password FROM auth_lookup_user(%s)", [email or ""])
        row = cur.fetchone()
    return UserLookup(*row) if row else None
