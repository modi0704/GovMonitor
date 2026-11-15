"""role_assignment.office_id (plain uuid since P1.1) becomes a foreign key to office (D23).

The column is kept; only the constraint is added, so existing rows survive.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_auth_lookup_function"),
        ("structure", "0002_rls"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(model_name="roleassignment", name="role_assignment_user_office"),
                migrations.RemoveIndex(model_name="roleassignment", name="role_assign_agency__cb5cc8_idx"),
                migrations.RemoveField(model_name="roleassignment", name="office_id"),
                migrations.AddField(
                    model_name="roleassignment",
                    name="office",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_assignments",
                        to="structure.office",
                    ),
                    preserve_default=False,
                ),
                migrations.AddConstraint(
                    model_name="roleassignment",
                    constraint=models.UniqueConstraint(fields=("user", "office"), name="role_assignment_user_office"),
                ),
                migrations.AddIndex(
                    model_name="roleassignment",
                    index=models.Index(fields=["agency", "office"], name="role_assign_agency_office"),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    [
                        'ALTER INDEX "role_assign_agency__cb5cc8_idx" RENAME TO "role_assign_agency_office"',
                        'ALTER TABLE "role_assignment" ADD CONSTRAINT "role_assignment_office_id_fk" '
                        'FOREIGN KEY ("office_id") REFERENCES "office" ("id") ON DELETE CASCADE '
                        "DEFERRABLE INITIALLY DEFERRED",
                        'CREATE INDEX IF NOT EXISTS "role_assignment_office_id_idx" ON "role_assignment" ("office_id")',
                    ],
                    [
                        'DROP INDEX IF EXISTS "role_assignment_office_id_idx"',
                        'ALTER TABLE "role_assignment" DROP CONSTRAINT "role_assignment_office_id_fk"',
                        'ALTER INDEX "role_assign_agency_office" RENAME TO "role_assign_agency__cb5cc8_idx"',
                    ],
                )
            ],
        )
    ]
