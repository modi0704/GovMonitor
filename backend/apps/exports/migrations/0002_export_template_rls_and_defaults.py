"""Row-level security for export_template (system rows readable by all) and the system defaults."""

from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS

SYSTEM_DEFAULTS = {
    "pptx": {
        "report_title": "Performance Monitoring Report",
        "primary_color": "1F4E79",
        "accent_color": "F2C14E",
        "actual_color": "2E8B57",
        "footer_text": "",
        "currency_symbol": "₱",
    },
    "xlsx": {"header_fill": "FFD965"},
}


def create_defaults(apps, schema_editor):
    ExportTemplate = apps.get_model("exports", "ExportTemplate")
    db = schema_editor.connection.alias
    for kind, settings in SYSTEM_DEFAULTS.items():
        ExportTemplate.objects.using(db).get_or_create(
            agency=None,
            kind=kind,
            is_default=True,
            defaults={"name": "System default", "settings": settings},
        )


def remove_defaults(apps, schema_editor):
    ExportTemplate = apps.get_model("exports", "ExportTemplate")
    ExportTemplate.objects.using(schema_editor.connection.alias).filter(agency=None).delete()


class Migration(migrations.Migration):
    dependencies = [("exports", "0001_initial")]

    operations = [
        EnableTenantRLS("export_template", allow_global_select=True),
        migrations.RunPython(create_defaults, remove_defaults),
    ]
