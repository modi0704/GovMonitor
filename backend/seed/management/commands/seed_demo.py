"""Build the demo agencies (MASTERPLAN P14.4). Idempotent: running it twice changes nothing.

Each agency gets an administrator and its structure, built through the same services the API
uses (no hard-coded behaviour). Later phases extend this command (plans, reports).
Demo passwords come from DEMO_PASSWORD.
"""

import os

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.structure import services as structure
from apps.structure.models import Office, OfficeGroup
from apps.tenancy import context, services
from apps.tenancy.models import Agency
from seed import plans as demo_plans
from seed import structures
from seed.api_client import ApiSession

DEMO_AGENCIES = [
    {
        "code": "sample-ministry",
        "name": "Sample Ministry",
        "levels": structures.MINISTRY_LEVELS,
        "tree": structures.MINISTRY_TREE,
        "groups": structures.MINISTRY_GROUPS,
        "root_code": "MIN",
    },
    {
        "code": "sample-bureau",
        "name": "Sample Bureau",
        "levels": structures.BUREAU_LEVELS,
        "tree": structures.BUREAU_TREE,
        "groups": {},
        "root_code": "BUR",
    },
]


def _build(parent: Office, tree: dict) -> int:
    created = 0
    for code, (name, children) in tree.items():
        office = Office.objects.filter(code__iexact=code).first()
        if office is None:
            office = structure.create_office(parent, name, code)
            created += 1
        created += _build(office, children)
    return created


class Command(BaseCommand):
    help = "Create or update the demo agencies. Safe to run twice."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD", "demo-password-2026")
        for spec in DEMO_AGENCIES:
            agency = Agency.objects.using(services.OWNER).filter(code=spec["code"]).first()
            if agency is None:
                agency = services.create_agency(
                    name=spec["name"],
                    code=spec["code"],
                    root_level_name=spec["levels"][0],
                    root_code=spec["root_code"],
                )
                self.stdout.write(f"created agency {agency.code}")
            email = f"admin@{spec['code']}.demo"
            if not User.objects.using(services.OWNER).filter(email=email).exists():
                services.create_agency_admin(
                    agency, email=email, full_name="Demo Administrator", password=password
                )
                self.stdout.write(f"created administrator {email}")
            with context.agency_context(agency.id):
                structure.set_level_names(spec["levels"])
                created = _build(structure.get_root(), spec["tree"])
                for name, codes in spec["groups"].items():
                    group, _ = OfficeGroup.objects.get_or_create(name=name)
                    structure.set_group_members(
                        group, list(Office.objects.filter(code__in=codes).values_list("id", flat=True))
                    )
                agency.settings = {**agency.settings, "setup_complete": True}
                Agency.objects.filter(pk=agency.pk).update(settings=agency.settings)
            if created:
                self.stdout.write(f"{agency.code}: {created} offices created")
            if spec["code"] == "sample-ministry":
                self._ministry_plans(email, password)
        self.stdout.write(f"seed_demo: done (demo administrators use DEMO_PASSWORD, default {password!r})")

    def _ministry_plans(self, email: str, password: str) -> None:
        """Fiscal year 2026 and approved plans, created through the public API (Phase 5 exit)."""
        api = ApiSession(email, password)
        years = {y["label"]: y for y in api.get("/api/v1/fiscal-years")}
        fy = (
            years.get("2026")
            or api.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
        )
        if fy["status"] == "draft":
            api.patch(f"/api/v1/fiscal-years/{fy['id']}", {"status": "open"})
        offices = {o["code"]: o for o in api.get("/api/v1/offices")}
        existing = {p["office"]["code"] for p in api.get("/api/v1/plans", fiscal_year=fy["id"])}
        rows_by_office = demo_plans.fixture_plans() or {"PME": demo_plans.worked_example_rows()}
        for code, rows in rows_by_office.items():
            if code in existing or code not in offices:
                continue
            plan = api.post(
                "/api/v1/plans", {"office_id": offices[code]["id"], "fiscal_year_id": fy["id"]}
            ).json()
            api.post(f"/api/v1/plans/{plan['id']}/save", {"rows": rows})
            api.post(f"/api/v1/plans/{plan['id']}/submit")
            api.post(f"/api/v1/plans/{plan['id']}/approve")
            self.stdout.write(f"sample-ministry: plan for {code} approved ({len(rows)} rows)")
