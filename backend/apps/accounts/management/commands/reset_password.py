"""Forgotten password on the server: list the administrator accounts, or give one a new temporary
password (the person chooses their own at the next sign-in). For installs without email.

    manage reset_password                      list agency administrators
    manage reset_password --email chief@x.gov  print a new temporary password for that account
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services
from apps.accounts.models import RoleAssignment, User
from apps.tenancy import context
from apps.tenancy.models import Agency

OWNER = "owner"


class Command(BaseCommand):
    help = "List agency administrators, or set a new temporary password for one account."

    def add_arguments(self, parser):
        parser.add_argument("--email", help="The account to reset. Omit to list the administrators.")

    def handle(self, *args, email=None, **options):
        if not email:
            self.list_admins()
            return
        user = User.objects.using(OWNER).filter(email=email.strip().lower()).first()
        if user is None:
            raise CommandError("No account has that email. Run without --email to list the administrators.")
        agency = Agency.objects.using(OWNER).get(pk=user.agency_id)
        if not user.is_active or not agency.is_active:
            raise CommandError(
                "That account (or its agency) is switched off, so it cannot sign in. "
                "Use one of the accounts listed without --email."
            )
        with context.agency_context(agency.id):
            temporary = services.admin_reset_password(User.objects.get(pk=user.pk))
        self.stdout.write(self.style.SUCCESS(f"New temporary password for {user.email}: {temporary}"))
        self.stdout.write("Sign in with it; the app then asks you to choose your own password.")

    def list_admins(self):
        rows = (
            RoleAssignment.objects.using(OWNER)
            .filter(level="admin", office__parent__isnull=True)
            .select_related("user", "user__agency")
            .order_by("user__agency__name", "user__email")
        )
        if not rows:
            self.stdout.write("No agency administrator yet. Run './run.sh setup' or './run.sh demo'.")
            return
        self.stdout.write("Agency administrators:")
        for r in rows:
            on = r.user.is_active and r.user.agency.is_active
            self.stdout.write(f"  {r.user.email:<40} {r.user.agency.name}{'' if on else '  (switched off)'}")
        self.stdout.write("Reset one with:  ./run.sh reset-password <email>")
