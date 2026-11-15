from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS

TABLES = [
    "fiscal_year",
    "reporting_period",
    "scoring_profile",
    "plan",
    "activity",
    "activity_target",
    "indicator",
    "indicator_target",
]


class Migration(migrations.Migration):
    dependencies = [("planning", "0001_initial")]

    operations = [EnableTenantRLS(t) for t in TABLES]
