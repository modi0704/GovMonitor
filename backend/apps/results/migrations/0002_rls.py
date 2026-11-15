from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [("results", "0001_initial")]

    operations = [EnableTenantRLS("period_result")]
