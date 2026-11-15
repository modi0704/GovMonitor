"""Tenancy: agency, platform owner accounts, support grants (MASTERPLAN 6.2)."""

import uuid

from django.db import models

from apps.tenancy import context


class TenantQuerySet(models.QuerySet):
    def bulk_create(self, objs, *args, **kwargs):
        agency_id = None
        for obj in objs:
            if obj.agency_id is None:
                agency_id = agency_id or context.require_agency_id()
                obj.agency_id = agency_id
        return super().bulk_create(objs, *args, **kwargs)


class TenantModel(models.Model):
    """Base for every tenant table: UUID key and ``agency_id`` filled from the current context.

    Each concrete subclass's migration must apply ``EnableTenantRLS`` (P1.2); the meta-test in
    P1.9 fails otherwise.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey("tenancy.Agency", on_delete=models.PROTECT, related_name="+", editable=False)

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.agency_id is None:
            self.agency_id = context.require_agency_id()
        super().save(*args, **kwargs)


class Agency(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        SUSPENDED = "suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=40, unique=True)
    logo_key = models.CharField(max_length=300, blank=True)
    fiscal_year_start_month = models.PositiveSmallIntegerField(default=1)
    timezone = models.CharField(max_length=64, default="Asia/Manila")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agency"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fiscal_year_start_month__gte=1, fiscal_year_start_month__lte=12),
                name="agency_fy_start_month_1_12",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE


class PlatformAdmin(models.Model):
    """The vendor's accounts. No ``agency_id``, no RLS; app_user has no privileges on this table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    password = models.CharField(max_length=128)
    totp_secret = models.CharField(max_length=64, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_admin"

    def __str__(self) -> str:
        return self.email

    def set_password(self, raw: str) -> None:
        from django.contrib.auth.hashers import make_password

        self.password = make_password(raw)

    def check_password(self, raw: str) -> bool:
        from django.contrib.auth.hashers import check_password

        return check_password(raw, self.password)


class SupportGrant(TenantModel):
    """Time-limited read access for one platform admin to one agency (P1.7)."""

    platform_admin = models.ForeignKey(PlatformAdmin, on_delete=models.PROTECT, related_name="+")
    granted_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    expires_at = models.DateTimeField()
    reason = models.TextField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "support_grant"
        indexes = [models.Index(fields=["agency", "platform_admin", "expires_at"])]
