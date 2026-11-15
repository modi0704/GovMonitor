from django.apps import AppConfig


class JobsConfig(AppConfig):
    name = "apps.jobs"
    label = "jobs"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from apps.jobs import worker  # noqa: F401 — registers built-in job handlers and schedulers
