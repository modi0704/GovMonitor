"""Rows in every tenant table for two agencies, used by the isolation tests (P1.9, P14.2).

When a phase adds a tenant table, add a builder to ``BUILDERS``: the isolation test fails for any
tenant table that has no rows in both agencies.
"""

from datetime import timedelta

from django.utils import timezone

from apps.tenancy import context
from apps.tenancy.models import PlatformAdmin, SupportGrant
from tests.factories import assign, make_agency, make_office, make_root, make_user


def _base(code):
    agency = make_agency(code)
    root = make_root(agency)
    child = make_office(root, f"{code.upper()}-1")
    user = make_user(agency, f"admin@{code}.gov")
    assign(user, root, "admin")
    return {"agency": agency, "root": root, "child": child, "user": user}


def _support_grant(objs, platform_admin):
    with context.agency_context(objs["agency"].id):
        SupportGrant.objects.create(
            platform_admin_id=platform_admin.id,
            granted_by=objs["user"],
            reason="isolation test",
            expires_at=timezone.now() + timedelta(hours=1),
        )


def _group(objs, shared):
    from apps.structure.models import OfficeGroup, OfficeGroupMember

    with context.agency_context(objs["agency"].id):
        group = OfficeGroup.objects.create(name="Group")
        OfficeGroupMember.objects.create(group=group, office=objs["child"])


# table name -> builder(objs, shared). Tables filled by _base are listed with None.
BUILDERS = {
    "agency": None,
    "user": None,
    "role_assignment": None,
    "org_level": None,
    "office": None,
    "support_grant": lambda objs, shared: _support_grant(objs, shared["platform_admin"]),
    "office_group": _group,
    "office_group_member": None,  # filled by _group
}


def seed_two_agencies():
    admin = PlatformAdmin(email="iso@vendor.example")
    admin.set_password("isolation-test-password")
    admin.save(using="owner")
    shared = {"platform_admin": admin}
    out = {}
    for code in ("iso-a", "iso-b"):
        objs = _base(code)
        for builder in BUILDERS.values():
            if builder:
                builder(objs, shared)
        out[code] = objs
    return out["iso-a"], out["iso-b"]
