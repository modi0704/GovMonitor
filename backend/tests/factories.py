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


def make_root(agency: Agency, name: str | None = None, code: str = "ROOT", level_name: str = "Agency"):
    """Create level 0 and the root office of an agency (idempotent)."""
    from apps.structure.models import Office, OrgLevel

    with context.agency_context(agency.id):
        level, _ = OrgLevel.objects.get_or_create(depth=0, defaults={"name": level_name})
        root = Office.objects.filter(parent__isnull=True).first()
        if root is None:
            root = Office.objects.create(level=level, name=name or agency.name, code=code)
        return root


def make_office(parent, code: str, name: str | None = None, level_name: str | None = None):
    from apps.structure.models import Office, OrgLevel

    with context.agency_context(parent.agency_id):
        depth = parent.depth + 1
        level, _ = OrgLevel.objects.get_or_create(
            depth=depth, defaults={"name": level_name or f"Level {depth}"}
        )
        return Office.objects.create(parent=parent, level=level, name=name or code, code=code)


def assign(user: User, office, level: str = "admin"):
    from apps.accounts.models import RoleAssignment

    with context.agency_context(user.agency_id):
        return RoleAssignment.objects.create(user=user, office=office, level=level)
