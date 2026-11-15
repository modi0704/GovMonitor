"""Test bootstrap.

The test database must be created and migrated by app_owner (so that app_owner owns the tables and
row-level security genuinely binds app_user), while tests run their queries as app_user through the
``default`` alias — exactly like production. Django always creates test databases through the
``default`` alias, so during setup we temporarily give ``default`` the owner's credentials.
"""

import pytest
from django.db import connections
from django.test import testcases


def _swap_credentials(alias: str, source: str) -> tuple[str, str]:
    conn = connections[alias]
    previous = (conn.settings_dict["USER"], conn.settings_dict["PASSWORD"])
    conn.close()
    conn.settings_dict["USER"] = connections[source].settings_dict["USER"]
    conn.settings_dict["PASSWORD"] = connections[source].settings_dict["PASSWORD"]
    return previous


@pytest.fixture(scope="session")
def django_db_setup(request, django_test_environment, django_db_blocker):
    from django.test.utils import setup_databases, teardown_databases

    with django_db_blocker.unblock():
        app_user, app_password = _swap_credentials("default", "owner")
        try:
            db_cfg = setup_databases(
                verbosity=0, interactive=False, keepdb=False, aliases={"default", "owner"}
            )
        finally:
            connections["default"].close()
            connections["default"].settings_dict["USER"] = app_user
            connections["default"].settings_dict["PASSWORD"] = app_password

    yield

    with django_db_blocker.unblock():
        connections.close_all()
        _swap_credentials("default", "owner")
        teardown_databases(db_cfg, verbosity=0)


# Transactional tests (``django_db(transaction=True)``) end with ``flush``, i.e. TRUNCATE, which
# app_user is deliberately not granted. Flush through the owner's credentials instead.
_original_fixture_teardown = testcases.TransactionTestCase._fixture_teardown


def _fixture_teardown_as_owner(self):
    if "default" not in self._databases_names(include_mirrors=False):
        return _original_fixture_teardown(self)
    previous = _swap_credentials("default", "owner")
    try:
        return _original_fixture_teardown(self)
    finally:
        conn = connections["default"]
        conn.close()
        conn.settings_dict["USER"], conn.settings_dict["PASSWORD"] = previous


testcases.TransactionTestCase._fixture_teardown = _fixture_teardown_as_owner
