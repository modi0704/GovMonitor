"""Single-agency installs (DEPLOYMENT_MODE=single): create the one agency and its administrator.

Idempotent: running it again changes nothing and reports what exists.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.tenancy import services
from apps.tenancy.models import Agency


class Command(BaseCommand):
    help = "Create the single agency, its root office and its first administrator."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--code", required=True)
        parser.add_argument("--admin-email", required=True)
        parser.add_argument("--admin-name", default="")
        parser.add_argument("--fiscal-year-start-month", type=int, default=1)
        parser.add_argument("--timezone", default="Asia/Manila")
        parser.add_argument("--root-level-name", default="Agency")

    def handle(self, *args, **o):
        code = o["code"].strip().lower()
        agencies = Agency.objects.using(services.OWNER)
        others = agencies.exclude(code=code)
        if others.exists():
            raise CommandError(
                f"This installation already holds agency '{others.first().code}'. "
                "Single mode allows exactly one agency."
            )
        agency = agencies.filter(code=code).first()
        if agency is None:
            agency = services.create_agency(
                name=o["name"],
                code=code,
                fiscal_year_start_month=o["fiscal_year_start_month"],
                timezone_name=o["timezone"],
                root_level_name=o["root_level_name"],
            )
            self.stdout.write(f"agency created: {agency.code} ({agency.name})")
        else:
            self.stdout.write(f"agency exists: {agency.code}")

        email = o["admin_email"].strip().lower()
        existing = User.objects.using(services.OWNER).filter(email=email).first()
        if existing is not None:
            if existing.agency_id != agency.id:
                raise CommandError("That email belongs to a user of another agency.")
            self.stdout.write(f"administrator exists: {email}")
            return
        new = services.create_agency_admin(agency, email=email, full_name=o["admin_name"])
        self.stdout.write(f"administrator created: {email}")
        self.stdout.write(
            f"temporary password (shown once, must be changed at first sign-in): {new.temporary_password}"
        )
