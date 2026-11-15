import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, connections


def test_core_settings():
    assert settings.TIME_ZONE == "UTC" and settings.USE_TZ
    assert settings.DATABASES["default"]["ATOMIC_REQUESTS"] is True
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert get_user_model()._meta.db_table == "user"


@pytest.mark.django_db(databases=["default", "owner"])
def test_roles_are_separated():
    with connection.cursor() as cur:
        cur.execute("SELECT current_user, (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)")
        user, bypass = cur.fetchone()
        assert user == settings.DB_APP_ROLE and bypass is False
        cur.execute("SELECT tableowner FROM pg_tables WHERE tablename = 'user'")
        assert cur.fetchone()[0] != user  # app_user owns nothing
    with connections["owner"].cursor() as cur:
        cur.execute("SELECT current_user")
        assert cur.fetchone()[0] != settings.DB_APP_ROLE


@pytest.mark.django_db
def test_app_user_cannot_create_tables():
    from django.db.utils import ProgrammingError

    with pytest.raises(ProgrammingError), connection.cursor() as cur:
        cur.execute("CREATE TABLE should_fail (id int)")
