"""Users and role assignments (MASTERPLAN 6.2)."""

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from apps.tenancy.models import TenantModel, TenantQuerySet


class UserQuerySet(TenantQuerySet):
    pass


class UserManager(BaseUserManager.from_queryset(UserQuerySet)):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(TenantModel, AbstractBaseUser):
    """A person who signs in to one agency. Email is unique across all agencies."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    totp_secret = models.CharField(max_length=64, null=True, blank=True)
    recovery_codes = models.JSONField(default=list, blank=True)  # password-hashed, single use (D24)
    is_active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True, db_column="last_login_at")
    email_opt_out = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        db_table = "user"

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email

    @property
    def has_2fa(self) -> bool:
        return bool(self.totp_secret)


class RoleAssignment(TenantModel):
    """A user's access level at one office, covering that office and everything beneath it (D1)."""

    class Level(models.TextChoices):
        ADMIN = "admin"
        READ_ONLY = "read_only"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    # Plain UUID until the office table exists; P1.8/P2.1 turn it into a foreign key (D23).
    office_id = models.UUIDField()
    level = models.CharField(max_length=16, choices=Level.choices)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "role_assignment"
        constraints = [
            models.UniqueConstraint(fields=["user", "office_id"], name="role_assignment_user_office")
        ]
        indexes = [models.Index(fields=["agency", "office_id"])]
