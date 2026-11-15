from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS


class Migration(migrations.Migration):
    dependencies = [("structure", "0003_officegroup_officegroupmember_and_more")]

    operations = [EnableTenantRLS("office_group"), EnableTenantRLS("office_group_member")]
