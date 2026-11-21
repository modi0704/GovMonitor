"""P14.2 — every API route, called by agency A's administrator with ids that belong to agency B,
answers 404 or 403 and changes nothing in B.

Routes are classified in three ways; a new route that is in none of them fails
``test_every_route_is_classified``:

* ids in the path — filled in automatically from ``B_IDS`` by parameter name;
* ids in the query string or body — the cases in ``REFERENCE_CASES``;
* no ids of another agency can be named — ``NO_FOREIGN_IDS`` (with the reason).

List filters that take an id (e.g. ``plans?fiscal_year=``) may answer 200 with no rows: they reveal
nothing. The platform area (vendor staff only) refuses agency sessions outright.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import get_resolver

from apps.accounts.models import RoleAssignment, User
from apps.alerts.models import Notification
from apps.audit.models import AuditLog
from apps.jobs.models import Job
from apps.planning.models import ScoringProfile
from apps.reporting.models import Attachment
from apps.structure.models import OfficeGroup, OrgLevel
from apps.tenancy import context
from apps.tenancy.models import PlatformAdmin, SupportGrant
from tests.reporting_helpers import PNG, client, pdf, reporting_world

# Committed like real requests: platform owners and support grants are written through the owner
# connection and must be visible to the application's own connection.
pytestmark = pytest.mark.django_db(databases=["default", "owner"], transaction=True)
UNSAFE = ("post", "put", "patch", "delete")
DENIED = (403, 404)


def routes():
    def walk(patterns, prefix=""):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            else:
                cls = getattr(p.callback, "view_class", None)
                if cls is None:
                    continue
                methods = [m for m in ("get", *UNSAFE) if hasattr(cls, m)]
                yield p.name, prefix + str(p.pattern), methods

    return [r for r in walk(get_resolver().url_patterns) if r[1].startswith(("api/v1/", "platform/api/"))]


# Routes through which no id of another agency can be named.
NO_FOREIGN_IDS = {
    "health": "public liveness check",
    "auth-csrf": "no ids",
    "auth-login": "email and password only",
    "auth-logout": "no ids",
    "auth-password": "own password",
    "auth-password-reset": "email only; silent",
    "auth-password-reset-confirm": "signed token carries agency and user; tested in test_auth_api",
    "auth-2fa": "own pending sign-in",
    "auth-2fa-setup": "own account",
    "auth-2fa-enable": "own account",
    "auth-2fa-disable": "own account",
    "me": "own account",
    "users": "lists/creates in the caller's agency (ids of offices in the body: REFERENCE_CASES)",
    "agency": "the caller's agency",
    "support-grants": "the caller's agency",
    "levels": "names only",
    "offices": "list (create with a parent id: REFERENCE_CASES)",
    "offices-directory": "the caller's agency",
    "groups": "list/create by name",
    "audit-log": "list filters return only the caller's rows (RLS)",
    "audit-log-csv": "same as audit-log",
    "fiscal-years": "list/create by label",
    "scoring-presets": "built-in presets",
    "jobs": "the caller's own jobs",
    "export-template": "kind is 'pptx', not an id; the caller's template",
    "export-template-logo": "the caller's template",
    "alert-rules": "the caller's agency",
    "notifications": "the caller's own notifications",
    "notifications-unread": "the caller's own notifications",
    "notifications-read-all": "the caller's own notifications",
}
PLATFORM = {"platform-login", "platform-logout", "platform-me", "platform-agencies", "platform-agency",
            "platform-agency-admins", "platform-agency-support"}  # fmt: skip


@pytest.fixture
def two():
    a = reporting_world("alpha")
    b = reporting_world("beta")
    boss_b = b["boss"]
    group = boss_b.post("/api/v1/groups", {"name": "Beta group"}).json()
    boss_b.put(f"/api/v1/groups/{group['id']}/members", {"office_ids": [str(b["div"].id)]})
    lineage, jan = b["acts"]["A"]["lineage_id"], b["periods"][1]["id"]
    boss_b.post("/api/v1/reports/save", {"office": str(b["div"].id), "period": jan,
                                         "activities": [{"lineage_id": lineage, "actual": "1"}]})  # fmt: skip
    boss_b.c.post(
        "/api/v1/attachments",
        {"target_type": "activity_actual", "lineage_id": lineage, "period_id": jan, "file": pdf()},
    )
    boss_b.post("/api/v1/exports/xlsx", {"scope": "office", "office_id": str(b["div"].id), "period_id": jan})
    ops = PlatformAdmin(email="iso2@vendor.example")
    ops.set_password("platform-passphrase-123")
    ops.save(using="owner")
    with context.agency_context(b["agency"].id):
        user_b = User.objects.get(email="div@beta.gov")
        ids = {
            "user_id": user_b.id,
            "assignment_id": RoleAssignment.objects.filter(user=user_b).first().id,
            "grant_id": SupportGrant.objects.using("owner")
            .create(
                agency_id=b["agency"].id,
                platform_admin_id=ops.id,
                granted_by=user_b,
                expires_at="2099-01-01T00:00:00Z",
                reason="test",
            )
            .id,  # fmt: skip
            "level_id": OrgLevel.objects.order_by("-depth").first().id,
            "office_id": b["div"].id,
            "group_id": OfficeGroup.objects.get().id,
            "row_id": AuditLog.objects.order_by("-id").first().id,
            "fy_id": b["fy"]["id"],
            "period_id": jan,
            "profile_id": ScoringProfile.objects.get().id,
            "plan_id": b["plan"]["id"],
            "attachment_id": Attachment.objects.get().id,
            "job_id": Job.objects.get().id,
            "notification_id": Notification.objects.create(
                user=user_b, type="cutoff_reminder", title="B only", dedupe_key="b-only"
            ).id,
            "agency_id": b["agency"].id,
            "kind": "pptx",
        }
        before = AuditLog.objects.count()
    return {"a": a, "b": b, "ids": ids, "b_audit_rows": before, "lineage": lineage, "jan": jan}


def fill(path: str, ids: dict) -> str:
    import re

    def sub(m):
        return str(ids[m.group(2)])

    return "/" + re.sub(r"<(\w+):(\w+)>", sub, path)


def call(c, method, url, body=None, query=None):
    if method == "get":
        return c.c.get(url, query or {})
    if method == "delete":
        return c.delete(url)
    return getattr(c, method)(url, body or {})


def send(c, method, url, data):
    return call(
        c, method, url, body=data if method != "get" else None, query=data if method == "get" else None
    )


def same_as_unknown_id(c, method, url, data, b_ids) -> bool:
    """A 400 about a referenced id is acceptable only if it is exactly what a made-up id gets:
    then the answer reveals nothing about agency B (D43)."""
    import json
    import uuid

    text = json.dumps(data)
    for value in b_ids:
        text = text.replace(str(value), str(uuid.uuid4()))
    first, other = send(c, method, url, data), send(c, method, url, json.loads(text))
    return first.status_code == other.status_code and first.content == other.content


def reference_cases(w):
    """(label, method, url, body or query) naming agency B's objects from agency A's session."""
    b, ids, lineage, jan = w["b"], w["ids"], w["lineage"], w["jan"]
    a = w["a"]
    b_div, a_root = str(b["div"].id), str(a["root"].id)
    month = {"office": b_div, "period": jan}
    fy_b = b["fy"]["id"]
    one_b = {"scope": "office", "office_id": b_div, "period_id": jan}
    return [
        ("dashboard", "get", "/api/v1/dashboard", month),
        ("dashboard (own office, B month)", "get", "/api/v1/dashboard", {"office": a_root, "period": jan}),
        ("dashboard-activities", "get", "/api/v1/dashboard/activities", month),
        ("dashboard-activity", "get", "/api/v1/dashboard/activity", {"lineage": lineage, "period": jan}),
        ("rankings", "get", "/api/v1/rankings", {"period": jan}),
        ("reports", "get", "/api/v1/reports", month),
        ("reports-save", "post", "/api/v1/reports/save",
         {**month, "activities": [{"lineage_id": lineage, "actual": "9"}]}),
        ("reports-preview", "post", "/api/v1/reports/preview", month),
        ("reports-submit", "post", "/api/v1/reports/submit", month),
        ("reports-return", "post", "/api/v1/reports/return", {**month, "note": "x"}),
        ("submission-board", "get", "/api/v1/submission-board", {"period": jan}),
        ("progress (B year)", "get", "/api/v1/progress", {"fiscal_year": fy_b}),
        ("progress (B month)", "get", "/api/v1/progress", {"period": jan}),
        ("attachments (list)", "get", "/api/v1/attachments",
         {"target_type": "activity_actual", "lineage_id": lineage, "period_id": jan}),
        ("plans (B office)", "post", "/api/v1/plans", {"office_id": b_div, "fiscal_year_id": fy_b}),
        ("plans (B year)", "post", "/api/v1/plans", {"office_id": a_root, "fiscal_year_id": fy_b}),
        ("role-assignments (B user)", "post", "/api/v1/role-assignments",
         {"user_id": str(ids["user_id"]), "office_id": a_root, "level": "admin"}),
        ("role-assignments (B office)", "post", "/api/v1/role-assignments",
         {"user_id": str(a["boss_user_id"]), "office_id": b_div, "level": "admin"}),
        ("offices (create under B office)", "post", "/api/v1/offices",
         {"parent_id": b_div, "name": "X", "code": "X1"}),
        ("offices-reorder", "post", "/api/v1/offices/reorder", {"parent_id": b_div, "order": [b_div]}),
        ("offices-import", "post", "/api/v1/offices/import", {"parent_id": b_div, "rows": "X - Y"}),
        ("results-preview", "post", "/api/v1/results/preview", {"fiscal_year_id": fy_b, "activities": []}),
        ("export-xlsx", "post", "/api/v1/exports/xlsx", one_b),
        ("export-xlsx (own office, B month)", "post", "/api/v1/exports/xlsx",
         {"scope": "office", "office_id": a_root, "period_id": jan}),
        ("export-pptx", "post", "/api/v1/exports/pptx", one_b),
        ("import-plan-template", "get", "/api/v1/imports/plan-template", {"fiscal_year_id": fy_b}),
        ("group-members (A group, B office)", "put", f"/api/v1/groups/{a['group_id']}/members",
         {"office_ids": [b_div]}),
        ("users (create with B office)", "post", "/api/v1/users",
         {"email": "new@alpha.gov", "full_name": "N",
          "assignments": [{"office_id": b_div, "level": "admin"}]}),
        ("office-move (own office under B office)", "post", f"/api/v1/offices/{a['other'].id}/move",
         {"parent_id": b_div}),
    ]  # fmt: skip


# Listed in reference_cases (or multipart cases below) — classification for the meta test.
REFERENCED = {
    "dashboard", "dashboard-activities", "dashboard-activity", "rankings", "reports", "reports-save",
    "reports-preview", "reports-submit", "reports-return", "submission-board", "progress", "attachments",
    "plans",
    "role-assignments", "offices-reorder", "offices-import", "results-preview", "export-xlsx", "export-pptx",
    "import-plan-template", "import-plan",
}  # fmt: skip


def test_every_route_is_classified():
    unclassified = [
        name for name, path, _ in routes()
        if "<" not in path and name not in NO_FOREIGN_IDS and name not in REFERENCED and name not in PLATFORM
    ]  # fmt: skip
    assert not unclassified, f"classify these routes in tests/test_cross_tenant_api.py: {unclassified}"


def test_ids_in_the_path_are_404_or_403(two):
    a_admin = two["a"]["boss"]
    seen = []
    for name, path, methods in routes():
        if "<" not in path or name in PLATFORM:
            continue
        url = fill(path, two["ids"])
        for method in methods:
            r = call(a_admin, method, url)
            seen.append(name)
            if name.startswith("export-template"):
                continue  # 'kind' is not an id: the caller's own template (NO_FOREIGN_IDS)
            assert r.status_code in DENIED, (
                f"{method.upper()} {url} ({name}) → {r.status_code} {r.content[:200]}"
            )
    assert len(seen) > 40
    assert_b_untouched(two)


def test_ids_in_queries_and_bodies_are_404_or_403(two):
    w = two
    with context.agency_context(w["a"]["agency"].id):
        w["a"]["boss_user_id"] = User.objects.get(email="boss@alpha.gov").id
        w["a"]["group_id"] = OfficeGroup.objects.create(name="Alpha group").id
    a_admin = w["a"]["boss"]
    b_ids = [str(v) for k, v in w["ids"].items() if k != "kind"] + [w["lineage"], str(w["b"]["fy"]["id"])]
    for label, method, url, data in reference_cases(w):
        r = send(a_admin, method, url, data)
        if r.status_code == 400:
            assert same_as_unknown_id(a_admin, method, url, data, b_ids), (
                f"{label}: 400 differs from a made-up id"
            )
            continue
        assert r.status_code in DENIED, f"{label}: {method.upper()} {url} → {r.status_code} {r.content[:200]}"
    # Multipart: attach a file to B's activity; import a plan into B's office or year.
    upload = a_admin.c.post(
        "/api/v1/attachments",
        {"target_type": "activity_actual", "lineage_id": w["lineage"], "period_id": w["jan"],
         "file": SimpleUploadedFile("p.png", PNG)},
    )  # fmt: skip
    assert upload.status_code in DENIED, upload.content
    for office, fy in ((w["b"]["div"].id, w["a"]["fy"]["id"]), (w["a"]["other"].id, w["b"]["fy"]["id"])):
        r = a_admin.c.post(
            "/api/v1/imports/plan",
            {
                "file": SimpleUploadedFile("plan.xlsx", _xlsx()),
                "office_id": str(office),
                "fiscal_year_id": fy,
            },
        )
        assert r.status_code in DENIED, r.content
    assert_b_untouched(w)


def test_list_filters_with_other_agency_ids_show_nothing(two):
    a_admin = two["a"]["boss"]
    r = a_admin.get("/api/v1/plans", fiscal_year=two["b"]["fy"]["id"])
    assert r.status_code in DENIED or r.json() == []
    r = a_admin.get("/api/v1/audit-log", office=str(two["b"]["div"].id))
    assert r.status_code in DENIED or r.json()["results"] == []


def test_the_platform_area_refuses_agency_sessions(two):
    a_admin = two["a"]["boss"]
    for name, path, methods in routes():
        if name not in PLATFORM or name in ("platform-login", "platform-logout"):
            continue
        for method in methods:
            r = call(a_admin, method, fill(path, two["ids"]))
            assert r.status_code in (401, 403, 404), f"{name} {method} → {r.status_code}"


def assert_b_untouched(w):
    """Nothing A did shows up in B: no audit row in B written by A's administrator."""
    with context.agency_context(w["b"]["agency"].id):
        by_a = AuditLog.objects.filter(actor_label="boss@alpha.gov").count()
        assert by_a == 0, list(
            AuditLog.objects.filter(actor_label="boss@alpha.gov").values("action", "entity_type")
        )
    assert client(w["b"], "boss").get(f"/api/v1/plans/{w['ids']['plan_id']}").status_code == 200


def _xlsx() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws["H8"], ws["I8"], ws["N8"], ws["O8"] = "A-1 Task", 1, "PLAN", 1
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
