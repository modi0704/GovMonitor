from django.apps import AppConfig


class ExportsConfig(AppConfig):
    name = "apps.exports"
    label = "exports"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from apps.exports import jobs  # noqa: F401 — registers the export job handlers
