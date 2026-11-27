"""The server-side reset for a forgotten password (installs without email)."""

import io

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import User
from apps.tenancy import context
from tests.reporting_helpers import reporting_world

pytestmark = pytest.mark.django_db(databases=["default", "owner"], transaction=True)


def run(*args):
    out = io.StringIO()
    call_command("reset_password", *args, stdout=out)
    return out.getvalue()


def test_lists_admins_then_resets_one():
    w = reporting_world()
    listing = run()
    assert "boss@alpha.gov" in listing and "div@alpha.gov" not in listing  # top-office admins only
    out = run("--email", "BOSS@alpha.gov")
    temporary = out.split(": ")[1].split()[0]
    with context.agency_context(w["agency"].id):
        user = User.objects.get(email="boss@alpha.gov")
        assert user.check_password(temporary) and user.must_change_password


def test_unknown_or_switched_off_accounts_are_refused():
    w = reporting_world()
    with pytest.raises(CommandError, match="No account"):
        run("--email", "nobody@alpha.gov")
    User.objects.using("owner").filter(email="boss@alpha.gov").update(is_active=False)
    with pytest.raises(CommandError, match="switched off"):
        run("--email", "boss@alpha.gov")
    assert w  # the world exists
