import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.tenancy.models import Agency


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_seed_demo_is_idempotent():
    call_command("seed_demo")
    call_command("seed_demo")
    assert set(Agency.objects.using("owner").values_list("code", flat=True)) == {
        "sample-ministry",
        "sample-bureau",
    }
    assert User.objects.using("owner").count() == 2
