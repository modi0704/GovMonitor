from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0001_initial"),
        ("accounts", "0002_initial"),
    ]

    operations = [
        EnableTenantRLS("agency", column="id"),
        EnableTenantRLS("support_grant"),
    ]
