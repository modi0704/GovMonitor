"""Audit log (MASTERPLAN 6.5, Phase 3). Append-only: app_user may INSERT and SELECT, nothing else."""

from django.db import models


class AuditLog(models.Model):
    class ActorType(models.TextChoices):
        USER = "user"
        PLATFORM_ADMIN = "platform_admin"
        SYSTEM = "system"

    id = models.BigAutoField(primary_key=True)
    # Null only for platform-level events (written through the owner connection).
    agency = models.ForeignKey(
        "tenancy.Agency", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_type = models.CharField(max_length=20, choices=ActorType.choices)
    actor_id = models.UUIDField(null=True, blank=True)
    actor_label = models.CharField(max_length=254, blank=True)  # email at the time (D26)
    action = models.CharField(max_length=40)
    entity_type = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    office_id = models.UUIDField(null=True, blank=True)  # office the entity belongs to (D26)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(fields=["agency", "at"], name="audit_agency_at"),
            models.Index(fields=["agency", "actor_id", "at"], name="audit_agency_actor"),
            models.Index(fields=["agency", "entity_type", "entity_id"], name="audit_agency_entity"),
            models.Index(fields=["agency", "office_id", "at"], name="audit_agency_office"),
            models.Index(fields=["agency", "id"], name="audit_agency_id"),  # latest row per agency (D33)
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("Audit rows are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit rows are append-only")
