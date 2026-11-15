"""Drive the public API from a management command (the demo seed loads plans this way, P5 exit)."""

import json

from django.conf import settings
from django.test import Client


class SeedApiError(RuntimeError):
    pass


class ApiSession:
    def __init__(self, email: str, password: str):
        host = next(
            (h for h in settings.ALLOWED_HOSTS if h not in ("*",) and not h.startswith(".")), "localhost"
        )
        self.client = Client(HTTP_HOST=host)
        r = self.post("/api/v1/auth/login", {"email": email, "password": password}, ok=False)
        if r.status_code != 200 or r.json().get("status") != "ok":
            raise SeedApiError(f"cannot sign in as {email}: {r.status_code} {r.content[:200]!r}")

    def _check(self, r, ok):
        if ok and not 200 <= r.status_code < 300:
            raise SeedApiError(
                f"{r.request['REQUEST_METHOD']} {r.request['PATH_INFO']}: {r.status_code} {r.content[:300]!r}"
            )
        return r

    def get(self, url, **params):
        return self._check(self.client.get(url, params), True).json()

    def post(self, url, data=None, ok=True):
        r = self.client.post(url, json.dumps(data or {}), content_type="application/json")
        return self._check(r, ok) if ok else r

    def patch(self, url, data=None):
        r = self.client.patch(url, json.dumps(data or {}), content_type="application/json")
        return self._check(r, True)
