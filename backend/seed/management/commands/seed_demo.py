"""Build the demo agencies (MASTERPLAN P14.4). Idempotent. Filled in as phases add data."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the demo agencies. Safe to run twice."

    def handle(self, *args, **options):
        self.stdout.write("seed_demo: nothing to seed yet (agencies arrive in Phase 1).")
