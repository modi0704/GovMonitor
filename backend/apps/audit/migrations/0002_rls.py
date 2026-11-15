from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]

    # Agencies read and insert only their own rows. Rows with agency_id NULL (platform events) are
    # invisible to app_user and are written through the owner connection. UPDATE/DELETE/TRUNCATE are
    # revoked from app_user after every migrate (apps/tenancy/db.py APPEND_ONLY_TABLES).
    operations = [EnableTenantRLS("audit_log")]
