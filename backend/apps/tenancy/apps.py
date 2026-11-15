from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _grant_after_migrate(sender, using, **kwargs):
    from apps.tenancy.db import apply_grants, apply_tenant_foreign_keys

    apply_grants(using)
    apply_tenant_foreign_keys(using)


class TenancyConfig(AppConfig):
    name = "apps.tenancy"
    label = "tenancy"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Run once per migrate, after the last app (dispatch_uid makes it idempotent per process).
        post_migrate.connect(_grant_after_migrate, dispatch_uid="tenancy.grant_after_migrate")
