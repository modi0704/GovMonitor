from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [("reporting", "0001_initial")]

    operations = [
        EnableTenantRLS(t) for t in ("office_submission", "activity_actual", "indicator_actual", "attachment")
    ]
