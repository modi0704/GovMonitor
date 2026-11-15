import uuid

import pytest

from apps.accounts.models import RoleAssignment, User
from apps.tenancy import context
from apps.tenancy.models import Agency


@pytest.mark.django_db
def test_tenant_rows_take_agency_from_context():
    agency_id = uuid.uuid4()
    with context.agency_context(agency_id):
        Agency.objects.create(id=agency_id, name="Agency A", code="a")
        user = User.objects.create_user("Someone@Example.org", "a-long-password-123", full_name="S")
        assert user.agency_id == agency_id and user.email == "someone@example.org"
        from apps.structure.models import Office, OrgLevel

        level = OrgLevel.objects.create(depth=0, name="Agency")
        root = Office.objects.create(level=level, name="A", code="A")
        assert root.path == f"/{root.id}/" and root.agency_id == agency_id
        RoleAssignment.objects.bulk_create([RoleAssignment(user=user, office=root, level="admin")])
        assert RoleAssignment.objects.get().agency_id == agency_id
    assert context.current_agency_id() is None


@pytest.mark.django_db
def test_writing_tenant_rows_without_agency_fails():
    with pytest.raises(context.NoAgencyContext):
        User(email="x@example.org").save()


@pytest.mark.django_db(transaction=True)
def test_set_agency_requires_transaction():
    with pytest.raises(RuntimeError, match="inside transaction.atomic"):
        context.set_agency(uuid.uuid4())
