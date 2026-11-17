"""Create a real workspace and retire recognizable built-in training accounts.

No plans or reports are generated. Training records are retained for recovery;
customized agencies and their users are never changed by the cleanup.
"""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts.models import RoleAssignment, User
from apps.tenancy import services
from apps.tenancy.models import Agency
from apps.tenancy.training import BUILT_IN_TRAINING, is_builtin_training


class Command(BaseCommand):
    help = "Set up your real agency and disable the built-in demo accounts without deleting records."

    def add_arguments(self, parser):
        parser.add_argument("--name")
        parser.add_argument("--code")
        parser.add_argument("--admin-email")
        parser.add_argument("--admin-name")
        parser.add_argument("--fiscal-year-start-month", type=int, default=1)
        parser.add_argument("--root-level-name", default="Agency")
        parser.add_argument("--noinput", action="store_true")

    def handle(self, *args, **options):
        prompts = {
            "name": "Official agency name: ",
            "code": "Agency short code (letters, numbers, hyphens): ",
            "admin_name": "Administrator's full name: ",
            "admin_email": "Administrator's email: ",
        }
        for field, prompt in prompts.items():
            value = options.get(field)
            if value is None and not options["noinput"]:
                try:
                    value = input(prompt)
                except (EOFError, KeyboardInterrupt) as error:
                    raise CommandError("Setup stopped before any changes were made.") from error
            options[field] = (value or "").strip()
        name, code = options["name"], options["code"].lower()
        email, full_name = options["admin_email"].lower(), options["admin_name"]
        if not name or len(name) > 200 or not full_name or len(full_name) > 200:
            raise CommandError("Enter the agency name and administrator's full name (up to 200 characters).")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", code) or len(code) > 40:
            raise CommandError("Use a short agency code of up to 40 letters, numbers, or hyphens.")
        if code in BUILT_IN_TRAINING or email.endswith(".demo"):
            raise CommandError("Use your real agency code and email, not a built-in demo account.")
        try:
            validate_email(email)
        except ValidationError as error:
            raise CommandError("Enter a valid administrator email.") from error
        if len(email) > 254:
            raise CommandError("The administrator email is too long.")
        if not 1 <= options["fiscal_year_start_month"] <= 12:
            raise CommandError("The fiscal year must start in a month from 1 to 12.")
        root_level = options["root_level_name"].strip()
        if not root_level or len(root_level) > 80:
            raise CommandError("Enter a root level name of up to 80 characters.")

        password = None
        retired, retained = [], []
        with transaction.atomic(using=services.OWNER):
            agencies = Agency.objects.using(services.OWNER)
            agency = agencies.filter(code=code).first()
            existing = User.objects.using(services.OWNER).filter(email=email).first()
            if agency and (agency.name != name or not agency.is_active):
                raise CommandError(
                    "That code belongs to a different or suspended agency. No changes were made."
                )
            if existing and (not agency or existing.agency_id != agency.id):
                raise CommandError("That email already belongs to another agency. No changes were made.")
            if existing and (
                not existing.is_active
                or not RoleAssignment.objects.using(services.OWNER)
                .filter(user=existing, level="admin", office__parent__isnull=True)
                .exists()
            ):
                raise CommandError(
                    "That account is not an active agency administrator. No changes were made."
                )
            if settings.DEPLOYMENT_MODE == "single" and (
                agencies.filter(status="active")
                .exclude(code=code)
                .exclude(code__in=BUILT_IN_TRAINING)
                .exists()
            ):
                raise CommandError("Single-agency mode already has a real agency. No changes were made.")
            # Check training identities before writing. Never treat a customized agency as disposable.
            training = []
            for training_code in BUILT_IN_TRAINING:
                candidate = agencies.filter(code=training_code).first()
                if candidate is None:
                    continue
                users = list(User.objects.using(services.OWNER).filter(agency=candidate))
                if is_builtin_training(candidate.code, candidate.name, [user.email for user in users]):
                    training.append((candidate, users))
                else:
                    retained.append(candidate.code)
            if settings.DEPLOYMENT_MODE == "single" and retained:
                raise CommandError("A customized training agency needs review before single-agency setup.")
            if agency is None:
                agency = services.create_agency(
                    name=name,
                    code=code,
                    fiscal_year_start_month=options["fiscal_year_start_month"],
                    root_level_name=root_level,
                )
            if existing is None:
                account = services.create_agency_admin(agency, email=email, full_name=full_name)
                password = account.temporary_password
            for candidate, users in training:
                services.set_agency_status(candidate, "suspended")
                for user in users:
                    user.is_active = False
                    user.save(using=services.OWNER, update_fields=["is_active"])
                retired.append(candidate.code)

        self.stdout.write(self.style.SUCCESS(f"Workspace ready: {agency.name} ({agency.code})."))
        self.stdout.write(f"Administrator: {email}")
        if password:
            self.stdout.write(f"Temporary password (shown once): {password}")
            self.stdout.write("Change this password at first sign-in. Keep it private.")
        else:
            self.stdout.write("Existing administrator kept. Your password was not changed.")
        if retired:
            self.stdout.write(f"Training agencies suspended; demo accounts disabled: {', '.join(retired)}.")
        if retained:
            self.stdout.write(
                self.style.WARNING(f"Customized agencies left untouched: {', '.join(retained)}.")
            )
        self.stdout.write("No plans, reports, or practice figures were created. No records were deleted.")
