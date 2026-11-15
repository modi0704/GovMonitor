from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [("alerts", "0001_initial")]

    operations = [EnableTenantRLS("alert_rule"), EnableTenantRLS("notification")]
