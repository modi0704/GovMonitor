"""P13.5: office-install licence — signature, banner window, read-only after expiry, seats."""

import base64
import datetime
import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.utils import timezone

from apps.tenancy import licence
from tests.factories import Json, api_client, assign, make_agency, make_root, make_user

pytestmark = pytest.mark.django_db
TOOL = Path(__file__).resolve().parents[4] / "tools" / "licence.py"


def tool():
    spec = importlib.util.spec_from_file_location("licence_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def vendor(settings, tmp_path):
    """A vendor key pair; the app trusts its public key; single-agency mode; licence path set."""
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    settings.LICENCE_PUBLIC_KEY = base64.b64encode(pub).decode()
    settings.DEPLOYMENT_MODE = "single"
    settings.LICENCE_FILE = str(tmp_path / "licence.json")
    licence._cache.clear()

    def issue(days=365, seats=10, tamper=False):
        expires = (timezone.localdate() + datetime.timedelta(days=days)).isoformat()
        doc = tool().sign_payload(
            base64.b64encode(raw).decode(), {"agency": "Office", "expires": expires, "seats": seats}
        )
        if tamper:
            doc["payload"]["seats"] = 9999
        Path(settings.LICENCE_FILE).write_text(json.dumps(doc))
        licence._cache.clear()

    return issue


@pytest.fixture
def office():
    agency = make_agency("office")
    root = make_root(agency)
    assign(make_user(agency, "chief@office.gov"), root, "admin")
    return {"agency": agency, "root": root, "chief": Json(api_client("chief@office.gov"))}


def test_multi_mode_needs_no_licence(settings):
    settings.DEPLOYMENT_MODE = "multi"
    assert licence.state().status == "not_required" and not licence.state().read_only


def test_statuses(vendor):
    vendor(days=200)
    assert licence.state().status == "valid" and licence.state().seats == 10
    vendor(days=20)
    s = licence.state()
    assert s.status == "expiring" and s.days_left == 20 and "20 days left" in s.message
    vendor(days=-1)
    assert licence.state().status == "expired" and licence.state().read_only
    vendor(tamper=True)
    assert licence.state().status == "invalid" and "not genuine" in licence.state().message


def test_missing_licence_is_read_only(vendor):
    assert licence.state().status == "missing" and licence.state().read_only


def test_expired_licence_keeps_reading_and_exporting_but_refuses_changes(vendor, office):
    vendor(days=-1)
    chief = office["chief"]
    me = chief.get("/api/v1/me").json()
    assert me["licence"]["status"] == "expired" and me["licence"]["read_only"] is True
    r = chief.post("/api/v1/fiscal-years", {"label": "2027", "start_year": 2027})
    assert r.status_code == 403 and r.json()["code"] == "licence_read_only"
    assert chief.get("/api/v1/offices").status_code == 200  # reading works
    assert chief.post("/api/v1/auth/logout").status_code in (200, 204)  # signing out works
    again = Json(api_client("chief@office.gov"))  # signing in works
    assert again.get("/api/v1/me").status_code == 200


def test_valid_licence_allows_changes_and_shows_a_banner_near_expiry(vendor, office):
    vendor(days=10)
    chief = office["chief"]
    assert chief.post("/api/v1/fiscal-years", {"label": "2027", "start_year": 2027}).status_code == 201
    banner = chief.get("/api/v1/me").json()["licence"]
    assert banner["status"] == "expiring" and banner["days_left"] == 10 and banner["seats_used"] == 1


def test_seat_limit_stops_new_users_only(vendor, office):
    vendor(seats=2)
    chief = office["chief"]
    body = {"email": "a@office.gov", "full_name": "A", "assignments": []}
    assert chief.post("/api/v1/users", body).status_code == 201  # 2 of 2
    r = chief.post("/api/v1/users", {**body, "email": "b@office.gov"})
    assert r.status_code == 403 and r.json()["code"] == "seat_limit"
    assert chief.get("/api/v1/users").status_code == 200


def test_cli_keygen_sign_show(tmp_path, capsys, settings):
    t = tool()
    t.main(["keygen", "--out", str(tmp_path / "k")])
    public = capsys.readouterr().out.split("public key: ")[1].strip()
    t.main(["sign", "--key", str(tmp_path / "k"), "--agency", "Office", "--expires", "2099-01-01",
            "--seats", "5", "--out", str(tmp_path / "l.json")])  # fmt: skip
    settings.LICENCE_PUBLIC_KEY = public
    payload = licence.verify((tmp_path / "l.json").read_text())
    assert payload["agency"] == "Office" and payload["seats"] == 5
