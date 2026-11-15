"""Platform-owner operations (P1.6, P1.7). These use the ``owner`` connection (app_owner, which
bypasses row-level security), so every query here names its agency explicitly."""

import uuid
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RoleAssignment, User
from apps.accounts.services import generate_temporary_password
from apps.structure.models import Office, OrgLevel
from apps.tenancy.models import Agency, PlatformAdmin, SupportGrant

OWNER = "owner"


class PlatformError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class NewAdmin:
    user: User
    temporary_password: str


def create_agency(
    *,
    name: str,
    code: str,
    fiscal_year_start_month: int = 1,
    timezone_name: str = "Asia/Manila",
    root_level_name: str = "Agency",
    root_code: str | None = None,
) -> Agency:
    """Create an agency with its level 0 and root office (exactly one root per agency, 6.3)."""
    code = code.strip().lower()
    with transaction.atomic(using=OWNER):
        if Agency.objects.using(OWNER).filter(code=code).exists():
            raise PlatformError("duplicate_code", f"An agency with code '{code}' already exists.")
        agency = Agency.objects.using(OWNER).create(
            id=uuid.uuid4(),
            name=name.strip(),
            code=code,
            fiscal_year_start_month=fiscal_year_start_month,
            timezone=timezone_name,
        )
        level = OrgLevel(agency=agency, depth=0, name=root_level_name)
        level.save(using=OWNER)
        root = Office(agency=agency, level=level, name=agency.name, code=(root_code or code).upper()[:40])
        root.save(using=OWNER)
    return agency


def root_office(agency: Agency) -> Office:
    return Office.objects.using(OWNER).get(agency=agency, parent__isnull=True)


def create_agency_admin(
    agency: Agency, *, email: str, full_name: str = "", password: str | None = None
) -> NewAdmin:
    """Create a user who is ``admin`` at the agency's root office, i.e. the agency administrator."""
    email = email.strip().lower()
    with transaction.atomic(using=OWNER):
        if User.objects.using(OWNER).filter(email=email).exists():
            raise PlatformError("duplicate_email", "A user with this email already exists.")
        temporary = password or generate_temporary_password()
        user = User(
            agency=agency, email=email, full_name=full_name.strip(), must_change_password=password is None
        )
        user.set_password(temporary)
        user.save(using=OWNER)
        RoleAssignment(agency=agency, user=user, office=root_office(agency), level="admin").save(using=OWNER)
    return NewAdmin(user=user, temporary_password=temporary)


def set_agency_status(agency: Agency, status: str) -> Agency:
    if status not in Agency.Status.values:
        raise PlatformError("bad_status", "Status must be 'active' or 'suspended'.")
    agency.status = status
    agency.save(using=OWNER, update_fields=["status"])
    return agency


def active_grant(platform_admin: PlatformAdmin, agency: Agency) -> SupportGrant | None:
    now = timezone.now()
    return (
        SupportGrant.objects.using(OWNER)
        .filter(agency=agency, platform_admin=platform_admin, expires_at__gt=now, revoked_at__isnull=True)
        .order_by("-expires_at")
        .first()
    )
