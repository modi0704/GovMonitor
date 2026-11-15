"""Create or update a platform-owner account (vendor staff). Idempotent."""

import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.models import PlatformAdmin


class Command(BaseCommand):
    help = "Create or update a platform admin (multi-agency mode)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--full-name", default="")
        parser.add_argument("--password", help="Omit to be prompted")

    def handle(self, *args, email, full_name, password, **opts):
        password = password or getpass.getpass("Password: ")
        try:
            validate_password(password)
        except Exception as exc:  # noqa: BLE001
            raise CommandError("; ".join(getattr(exc, "messages", [str(exc)]))) from exc
        admin, created = PlatformAdmin.objects.using("owner").get_or_create(
            email=email.strip().lower(), defaults={"full_name": full_name}
        )
        if full_name:
            admin.full_name = full_name
        admin.set_password(password)
        admin.is_active = True
        admin.save(using="owner")
        self.stdout.write(f"platform admin {'created' if created else 'updated'}: {admin.email}")
