from django.apps import AppConfig


class AlertsConfig(AppConfig):
    name = "apps.alerts"
    label = "alerts"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from apps.alerts import jobs  # noqa: F401 — registers the alert_scan job and its scheduler
