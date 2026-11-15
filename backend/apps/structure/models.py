"""Agency structure: levels, offices (any depth), office groups (MASTERPLAN 6.3)."""

from django.contrib.postgres.indexes import OpClass
from django.db import models
from django.db.models.functions import Upper

from apps.tenancy.models import TenantModel


class OrgLevel(TenantModel):
    depth = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=80)

    class Meta:
        db_table = "org_level"
        ordering = ["depth"]
        constraints = [models.UniqueConstraint(fields=["agency", "depth"], name="org_level_agency_depth")]

    def __str__(self) -> str:
        return f"{self.depth}: {self.name}"


class Office(TenantModel):
    """A node of the agency tree. ``path`` is the materialised path ``/<root>/<…>/<own id>/``."""

    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    level = models.ForeignKey(OrgLevel, on_delete=models.PROTECT, related_name="offices")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=40)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    path = models.TextField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "office"
        ordering = ["path"]
        constraints = [
            models.UniqueConstraint("agency", Upper("code"), name="office_agency_code_ci"),
            models.UniqueConstraint(
                fields=["agency"], condition=models.Q(parent__isnull=True), name="office_one_root_per_agency"
            ),
        ]
        indexes = [
            models.Index(OpClass("path", name="text_pattern_ops"), name="office_path_pattern"),
            models.Index(fields=["agency", "parent", "sort_order"], name="office_agency_parent"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    @property
    def depth(self) -> int:
        return self.path.strip("/").count("/")

    @property
    def ancestor_ids(self) -> list[str]:
        """Ids from the root down to the parent (excluding self)."""
        return self.path.strip("/").split("/")[:-1]

    def compute_path(self) -> str:
        if self.parent_id is None:
            return f"/{self.id}/"
        parent_path = (
            self.parent.path
            if self.parent
            else Office.objects.values_list("path", flat=True).get(pk=self.parent_id)
        )
        return f"{parent_path}{self.id}/"

    def save(self, *args, **kwargs):
        if not self.path:
            self.path = self.compute_path()
        super().save(*args, **kwargs)
