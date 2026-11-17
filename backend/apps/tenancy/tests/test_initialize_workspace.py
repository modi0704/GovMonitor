from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import CommandError, call_command

from apps.tenancy.training import is_builtin_training


@pytest.mark.parametrize(
    ("code", "name", "emails", "expected"),
    [
        ("sample-ministry", "Sample Ministry", ["admin@sample-ministry.demo"], True),
        ("sample-bureau", "Sample Bureau", ["admin@sample-bureau.demo"], True),
        ("sample-ministry", "Actual Ministry", ["admin@sample-ministry.demo"], False),
        ("real-agency", "Sample Ministry", ["admin@sample-ministry.demo"], False),
        ("sample-ministry", "Sample Ministry", [], False),
        ("sample-ministry", "Sample Ministry", ["admin@sample-ministry.demo", "staff@office.gov.ph"], False),
    ],
)
def test_only_original_training_agencies_are_retired(code, name, emails, expected):
    assert is_builtin_training(code, name, emails) is expected


@pytest.mark.parametrize(
    "override",
    [
        {"admin_email": "admin@sample-ministry.demo"},
        {"code": "sample-ministry"},
        {"code": "invalid code"},
        {"admin_email": "invalid-email"},
        {"fiscal_year_start_month": 13},
        {"name": ""},
        {"admin_name": ""},
    ],
)
def test_invalid_details_are_rejected_before_any_database_write(override):
    details = {
        "name": "Performance Monitoring Office",
        "code": "pmo",
        "admin_email": "admin@office.gov.ph",
        "admin_name": "Office Administrator",
        "noinput": True,
        **override,
    }
    with patch("apps.tenancy.management.commands.initialize_workspace.transaction.atomic") as atomic:
        with pytest.raises(CommandError):
            call_command("initialize_workspace", **details)
        atomic.assert_not_called()


def test_setup_reuses_an_existing_admin_and_does_not_create_sample_reports(settings):
    settings.DEPLOYMENT_MODE = "multi"
    target = "apps.tenancy.management.commands.initialize_workspace"
    agency = SimpleNamespace(id="real", name="Performance Monitoring Office", code="pmo", is_active=True)
    user = MagicMock(agency_id="real", is_active=True)
    agency_manager = MagicMock()
    agency_manager.filter.return_value.first.side_effect = [agency, None, None]
    user_manager = MagicMock()
    user_manager.filter.return_value.first.return_value = user
    out = StringIO()
    with (
        patch(f"{target}.transaction.atomic"),
        patch(f"{target}.Agency.objects.using", return_value=agency_manager),
        patch(f"{target}.User.objects.using", return_value=user_manager),
        patch(f"{target}.RoleAssignment.objects.using") as roles,
        patch(f"{target}.services.create_agency") as create_agency,
        patch(f"{target}.services.create_agency_admin") as create_admin,
    ):
        roles.return_value.filter.return_value.exists.return_value = True
        call_command(
            "initialize_workspace",
            name="Performance Monitoring Office",
            code="pmo",
            admin_email="admin@office.gov.ph",
            admin_name="Office Administrator",
            noinput=True,
            stdout=out,
        )
    create_agency.assert_not_called()
    create_admin.assert_not_called()
    assert "Your password was not changed" in out.getvalue()
    assert "No plans, reports, or practice figures were created" in out.getvalue()


@pytest.mark.parametrize("has_real_user", [False, True])
def test_new_setup_disables_only_untouched_demo_accounts(settings, has_real_user):
    settings.DEPLOYMENT_MODE = "multi"
    target = "apps.tenancy.management.commands.initialize_workspace"
    real = SimpleNamespace(id="real", name="Performance Monitoring Office", code="pmo")
    training = SimpleNamespace(id="training", name="Sample Ministry", code="sample-ministry")
    demo_user = MagicMock(email="admin@sample-ministry.demo", is_active=True)
    users = [demo_user]
    if has_real_user:
        users.append(MagicMock(email="staff@office.gov.ph", is_active=True))
    agency_manager = MagicMock()
    agency_manager.filter.return_value.first.side_effect = [None, training, None]
    user_manager = MagicMock()
    user_manager.filter.return_value.first.return_value = None
    user_manager.filter.return_value.__iter__.side_effect = lambda: iter(users)
    out = StringIO()
    with (
        patch(f"{target}.transaction.atomic"),
        patch(f"{target}.Agency.objects.using", return_value=agency_manager),
        patch(f"{target}.User.objects.using", return_value=user_manager),
        patch(f"{target}.services.create_agency", return_value=real) as create_agency,
        patch(f"{target}.services.create_agency_admin") as create_admin,
        patch(f"{target}.services.set_agency_status") as suspend,
    ):
        create_admin.return_value.temporary_password = "one-time-test-password"
        call_command(
            "initialize_workspace",
            name=real.name,
            code=real.code,
            admin_email="admin@office.gov.ph",
            admin_name="Office Administrator",
            noinput=True,
            stdout=out,
        )
    create_agency.assert_called_once()
    create_admin.assert_called_once()
    if has_real_user:
        suspend.assert_not_called()
        demo_user.save.assert_not_called()
        assert "left untouched" in out.getvalue()
    else:
        suspend.assert_called_once_with(training, "suspended")
        assert demo_user.is_active is False
        demo_user.save.assert_called_once_with(using="owner", update_fields=["is_active"])
