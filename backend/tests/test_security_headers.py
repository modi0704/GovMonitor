"""P13.1: security headers on every response, structured logs, production settings."""

import json
import logging

import pytest

from config.logs import JsonFormatter

pytestmark = pytest.mark.django_db


def test_every_response_carries_a_strict_content_security_policy(client):
    for path in ("/sign-in", "/api/v1/health", "/api/v1/me"):
        r = client.get(path)
        csp = r["Content-Security-Policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp, path
        assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
        # No outside origin anywhere: only 'self', data:/blob: images and keywords.
        sources = {t for part in csp.split(";") for t in part.split()[1:]}
        assert sources <= {"'self'", "'none'", "'unsafe-inline'", "data:", "blob:"}, sources
        assert r["X-Content-Type-Options"] == "nosniff"
        assert "camera=(self)" in r["Permissions-Policy"]


def test_json_log_lines_carry_extra_fields_and_exceptions():
    record = logging.makeLogRecord(
        {
            "name": "worker",
            "levelname": "WARNING",
            "msg": "job %s failed",
            "args": ("j1",),
            "request_id": "abc",
        }
    )
    data = json.loads(JsonFormatter().format(record))
    assert data["message"] == "job j1 failed" and data["level"] == "WARNING"
    assert data["logger"] == "worker" and data["request_id"] == "abc"
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()
    assert "ValueError: boom" in json.loads(JsonFormatter().format(record))["exception"]


PROBE = (
    "import json, config.settings.prod as p; print(json.dumps({'debug': p.DEBUG, "
    "'session': p.SESSION_COOKIE_SECURE, 'csrf': p.CSRF_COOKIE_SECURE, 'hsts': p.SECURE_HSTS_SECONDS, "
    "'log': p.LOGGING['handlers']['console']['formatter'], "
    "'csp': 'config.security.SecurityHeadersMiddleware' in p.MIDDLEWARE}))"
)


def prod_settings(**env):
    """Import the production settings in a fresh interpreter with exactly this environment."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    base = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "SECURE_SSL", "LOG_FORMAT")}
    base.pop("DJANGO_SETTINGS_MODULE", None)
    r = subprocess.run(  # noqa: S603 — this interpreter, a fixed snippet
        [sys.executable, "-c", PROBE],
        cwd=Path(__file__).resolve().parents[1],
        env={**base, **env},
        capture_output=True,
        text=True,
        timeout=60,
    )
    return r


GOOD = {
    "SECRET_KEY": "a-real-secret-key-for-the-test-0123456789",
    "DATABASE_URL": "postgres://u:p@db/x",
    "DATABASE_ADMIN_URL": "postgres://o:p@db/x",
}


@pytest.mark.parametrize(("secure", "hsts"), [("1", 31536000), ("0", 0)])
def test_production_settings(secure, hsts):
    r = prod_settings(**GOOD, SECURE_SSL=secure)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout.strip().splitlines()[-1])
    on = secure == "1"
    assert got == {"debug": False, "session": on, "csrf": on, "hsts": hsts, "log": "json", "csp": True}


def test_production_refuses_the_development_secret():
    r = prod_settings(**{k: v for k, v in GOOD.items() if k != "SECRET_KEY"})
    assert r.returncode != 0 and "Set SECRET_KEY for production" in r.stderr
