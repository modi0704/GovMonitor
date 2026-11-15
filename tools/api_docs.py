"""Writes docs/API.md from the URL routes and the views' docstrings (P14.5).

    cd backend && .venv/bin/python ../tools/api_docs.py

tests/test_api_docs.py fails when a route is missing from docs/API.md, so re-run this after adding
or renaming an endpoint.
"""

import inspect
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.urls import get_resolver  # noqa: E402

AREAS = [
    ("auth/", "Sign-in and account"), ("me", "Sign-in and account"), ("users", "Users and access"),
    ("role-assignments", "Users and access"), ("agency", "Agency"), ("support-grants", "Agency"),
    ("levels", "Structure"), ("offices", "Structure"), ("groups", "Structure"), ("audit-log", "Audit log"),
    ("fiscal-years", "Fiscal years and scoring"), ("periods", "Fiscal years and scoring"),
    ("scoring-", "Fiscal years and scoring"), ("plans", "Plans"), ("results", "Results"),
    ("dashboard", "Results"), ("rankings", "Results"), ("reports", "Monthly reporting"),
    ("submission-board", "Monthly reporting"), ("attachments", "Monthly reporting"),
    ("jobs", "Exports and imports"),
    ("exports", "Exports and imports"), ("imports", "Exports and imports"),
    ("export-templates", "Exports and imports"), ("alert-rules", "Alerts"), ("notifications", "Alerts"),
    ("health", "Service"),
]  # fmt: skip


def routes():
    def walk(patterns, prefix=""):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            else:
                yield prefix + str(p.pattern), p

    for path, p in walk(get_resolver().url_patterns):
        if path.startswith(("api/v1/", "platform/api/")):
            yield "/" + re.sub(r"<\w+:(\w+)>", r"{\1}", path), p


def summary(cls, method: str, route: str) -> str:
    """The view's own words: its method's docstring, else its class docstring, else SUMMARIES."""
    own = cls.__dict__.get(method) if cls else None
    doc = inspect.cleandoc(own.__doc__) if own is not None and own.__doc__ else ""
    if not doc and cls is not None and cls.__dict__.get("__doc__"):
        doc = inspect.cleandoc(cls.__dict__["__doc__"])
    if not doc:
        doc = SUMMARIES.get(f"{method.upper()} {route}", SUMMARIES.get(route, ""))
    first = " ".join(doc.split("\n\n")[0].split())
    return first.replace("|", "\\|")


def area(path: str) -> str:
    if path.startswith("/platform/"):
        return "Platform owners (multi-agency mode only)"
    rest = path.removeprefix("/api/v1/")
    return next((name for prefix, name in AREAS if rest.startswith(prefix)), "Other")


def main() -> None:
    grouped: dict[str, list] = {}
    for path, p in routes():
        cls = getattr(p.callback, "view_class", None)
        methods = [m for m in ("get", "post", "put", "patch", "delete") if cls and hasattr(cls, m)] or ["get"]
        for m in methods:
            grouped.setdefault(area(path), []).append((path, m.upper(), p.name, summary(cls, m, p.name)))
    order = list(
        dict.fromkeys([name for _, name in AREAS] + ["Other", "Platform owners (multi-agency mode only)"])
    )
    out = [HEADER]
    for name in order:
        if name not in grouped:
            continue
        out += [f"## {name}", "", "| Method | Path | Name | What it does |", "|---|---|---|---|"]
        for path, method, route, text in grouped[name]:
            out.append(f"| {method} | `{path}` | `{route}` | {text} |")
        out.append("")
    (ROOT / "docs" / "API.md").write_text("\n".join(out))
    print(f"docs/API.md: {sum(len(v) for v in grouped.values())} operations")


# Descriptions for views without a docstring of their own ("METHOD route-name": text).
SUMMARIES: dict[str, str] = json.loads((Path(__file__).with_name("api_summaries.json")).read_text())

HEADER = """# GovMonitor — API reference

Generated from the code by `tools/api_docs.py`; do not edit by hand.

## Conventions

* **Base path** `/api/v1/`. JSON in and out (multipart for file uploads). Times are ISO 8601 in UTC;
  amounts and quantities are decimal strings (e.g. `"1250.50"`); ids are UUIDs.
* **Sign-in** with `POST /api/v1/auth/login` (`{"email", "password"}`); the session cookie
  `gm_session` then authenticates every call. Call `GET /api/v1/auth/csrf` first and send the
  `gm_csrftoken` cookie's value as the `X-CSRFToken` header on every POST, PUT, PATCH and DELETE.
* **Scope**: every answer is limited to the caller's agency (database row-level security) and to the
  offices beneath their assignments. Ids outside that scope answer **404**, never revealing that they
  exist. Read-only users get **403** on changes; agency-wide settings need an agency administrator.
* **Errors**: `{"detail": "...", "code": "..."}` or field errors `{"field": ["message"]}` with
  400; 401 when not signed in (`code` `not_authenticated` or `session_expired`); 403, 404, 409 for
  conflicts (e.g. a month already locked), 429 when rate-limited.
* **Audit**: every successful change writes an audit-log row (who, what, before/after).
* **Background work** (exports, imports) returns a job (`202`); poll `GET /api/v1/jobs/{job_id}`
  and download from `download_url` when `status` is `done`.
* **Background polls** should send `X-Background: 1` so they do not count as user activity for
  the idle sign-out.
* **Read-only installs**: without a valid licence (office installs) changes answer 403 with
  `code` `licence_read_only`; reading and exports keep working.

"""

if __name__ == "__main__":
    main()
