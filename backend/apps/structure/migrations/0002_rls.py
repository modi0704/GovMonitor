from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [("structure", "0001_initial")]

    operations = [EnableTenantRLS("org_level"), EnableTenantRLS("office")]
