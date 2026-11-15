import pytest
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory

from apps.accounts.lookup import lookup_user_by_email
from apps.accounts.models import User
from apps.tenancy.middleware import SESSION_AGENCY_KEY, TenantMiddleware
from apps.tenancy.worker import run_in_agency
from tests.factories import make_agency, make_user


def _setting():
    with connection.cursor() as cur:
        cur.execute("SELECT current_setting('app.agency_id', true)")
        return cur.fetchone()[0]


@pytest.mark.django_db
def test_middleware_sets_agency_from_session_for_the_request():
    agency = make_agency("a")
    seen = {}

    def view(request):
        seen["setting"] = _setting()
        seen["users"] = User.objects.count()
        return HttpResponse("ok")

    make_user(agency, "a@example.org")
    request = RequestFactory().get("/")
    request.session = {SESSION_AGENCY_KEY: str(agency.id)}
    TenantMiddleware(view)(request)
    assert seen == {"setting": str(agency.id), "users": 1}
    assert request.agency_id == agency.id

    anonymous = RequestFactory().get("/")
    anonymous.session = {}
    TenantMiddleware(view)(anonymous)
    assert seen == {"setting": "", "users": 0}


@pytest.mark.django_db
def test_middleware_rolls_back_on_server_error():
    agency = make_agency("a")

    def failing_view(request):
        User.objects.create_user("new@example.org", "x" * 14)
        return HttpResponse(status=500)

    request = RequestFactory().post("/")
    request.session = {SESSION_AGENCY_KEY: str(agency.id)}
    TenantMiddleware(failing_view)(request)
    assert run_in_agency(agency.id, lambda: User.objects.filter(email="new@example.org").exists()) is False


@pytest.mark.django_db
def test_security_definer_lookup_works_without_agency():
    a = make_agency("a")
    user = make_user(a, "Person@Example.org")
    assert User.objects.count() == 0  # nothing visible with no agency set
    found = lookup_user_by_email("  PERSON@example.org ")
    assert found is not None and found.id == user.id and found.agency_id == a.id
    assert found.password.startswith("md5$")  # test hasher
    assert lookup_user_by_email("nobody@example.org") is None


@pytest.mark.django_db
def test_worker_helper_scopes_queries():
    a, b = make_agency("a"), make_agency("b")
    make_user(a, "1@a.org")
    make_user(a, "2@a.org")
    make_user(b, "1@b.org")
    assert run_in_agency(a.id, User.objects.count) == 2
    assert run_in_agency(b.id, User.objects.count) == 1
