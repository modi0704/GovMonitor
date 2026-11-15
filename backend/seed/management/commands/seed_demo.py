"""Build the demo agencies (MASTERPLAN P14.4). Idempotent: running it twice changes nothing.

Phase 1 content: two agencies, each with a root office and an administrator. Later phases extend
this command (structure, plans, reports). Demo passwords come from DEMO_PASSWORD.
"""

import os

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.tenancy import services
from apps.tenancy.models import Agency

DEMO_AGENCIES = [
    {"code": "sample-ministry", "name": "Sample Ministry", "root_level_name": "Ministry", "fy": 1},
    {"code": "sample-bureau", "name": "Sample Bureau", "root_level_name": "Bureau", "fy": 1},
]


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
                    fiscal_year_start_month=spec["fy"],
                    root_level_name=spec["root_level_name"],
                )
                self.stdout.write(f"created agency {agency.code}")
            email = f"admin@{spec['code']}.demo"
            if not User.objects.using(services.OWNER).filter(email=email).exists():
                services.create_agency_admin(
                    agency, email=email, full_name="Demo Administrator", password=password
                )
                self.stdout.write(f"created administrator {email}")
        self.stdout.write(f"seed_demo: done (demo administrators use DEMO_PASSWORD, default {password!r})")
