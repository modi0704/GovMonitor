from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_initial")]

    operations = [
        EnableTenantRLS("user"),
        EnableTenantRLS("role_assignment"),
    ]
