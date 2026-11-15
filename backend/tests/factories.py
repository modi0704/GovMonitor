"""Small helpers shared by tests: build agencies and users under the right agency context."""

import uuid

from apps.accounts.models import User
from apps.tenancy import context
from apps.tenancy.models import Agency

DEFAULT_PASSWORD = "correct-horse-battery-staple"


def make_agency(code: str, name: str | None = None, **extra) -> Agency:
    agency_id = uuid.uuid4()
    with context.agency_context(agency_id):
        return Agency.objects.create(id=agency_id, code=code, name=name or code.upper(), **extra)


def make_user(agency: Agency, email: str, password: str = DEFAULT_PASSWORD, **extra) -> User:
    extra.setdefault("must_change_password", False)
    with context.agency_context(agency.id):
        return User.objects.create_user(email, password, **extra)
