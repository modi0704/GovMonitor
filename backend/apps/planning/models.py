"""Planning: fiscal years, periods, scoring profiles, plans, activities, indicators (MASTERPLAN 6.4)."""

import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.tenancy.models import TenantModel

MONEY = {"max_digits": 18, "decimal_places": 2}
QTY = {"max_digits": 18, "decimal_places": 4}
RATIO = {"max_digits": 14, "decimal_places": 10}


class FiscalYear(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft"
        OPEN = "open"
        CLOSED = "closed"

    label = models.CharField(max_length=40)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fiscal_year"
        ordering = ["-start_date"]
        constraints = [models.UniqueConstraint(fields=["agency", "label"], name="fiscal_year_agency_label")]

    def __str__(self) -> str:
        return self.label


class ReportingPeriod(TenantModel):
    """One month of a fiscal year (D9). Lives with planning because creating a fiscal year creates
    its twelve periods (D28)."""

    class Status(models.TextChoices):
        OPEN = "open"
        LOCKED = "locked"

    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE, related_name="periods")
    month_index = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    start_date = models.DateField()
    end_date = models.DateField()
    cutoff_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    locked_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reporting_period"
        ordering = ["fiscal_year", "month_index"]
        constraints = [
            models.UniqueConstraint(fields=["fiscal_year", "month_index"], name="reporting_period_fy_month"),
            models.CheckConstraint(
                condition=models.Q(month_index__gte=1, month_index__lte=12),
                name="reporting_period_month_1_12",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.fiscal_year.label} M{self.month_index:02d}"

    @property
    def is_locked(self) -> bool:
        return self.status == self.Status.LOCKED


class ScoringProfile(TenantModel):
    """One per fiscal year (6.4). ``version`` goes up by one on every change."""

    fiscal_year = models.OneToOneField(FiscalYear, on_delete=models.CASCADE, related_name="profile")
    preset = models.CharField(max_length=40, default="workbook_compatible")
    weighting = models.CharField(max_length=20, default="cost_share")
    cap_at_100 = models.BooleanField(default=False)
    on_time_tolerance = models.DecimalField(default=Decimal("0"), **RATIO)
    label_ahead = models.CharField(max_length=30, default="ADVANCED")
    label_on_time = models.CharField(max_length=30, default="ON-TIME")
    label_delayed = models.CharField(max_length=30, default="DELAYED")
    rollup = models.CharField(max_length=20, default="budget_weighted")
    indicator_weighting = models.CharField(max_length=20, default="equal")
    indicator_rollup = models.CharField(max_length=20, default="all_indicators")
    ranking_metric = models.CharField(max_length=30, default="cumulative_actual")
    mov_required = models.BooleanField(default=False)
    auto_lock = models.BooleanField(default=False)
    cutoff_day = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1), MaxValueValidator(28)]
    )
    show_actual_amounts = models.BooleanField(default=False)  # P6.7 actual-amount column (D7)
    version = models.PositiveIntegerField(default=1)

    ENGINE_FIELDS = (
        "preset",
        "weighting",
        "cap_at_100",
        "on_time_tolerance",
        "label_ahead",
        "label_on_time",
        "label_delayed",
        "rollup",
        "indicator_weighting",
        "indicator_rollup",
        "ranking_metric",
    )

    class Meta:
        db_table = "scoring_profile"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cutoff_day__gte=1, cutoff_day__lte=28), name="scoring_profile_cutoff_1_28"
            )
        ]

    def to_engine(self):
        from apps.scoring.types import Profile

        return Profile(**{f: getattr(self, f) for f in self.ENGINE_FIELDS})

    def snapshot(self) -> dict:
        from apps.audit.services import jsonable

        names = (
            *self.ENGINE_FIELDS,
            "mov_required",
            "auto_lock",
            "cutoff_day",
            "show_actual_amounts",
            "version",
        )
        return {f: jsonable(getattr(self, f)) for f in names}


class Plan(TenantModel):
    """One office's work and financial plan for one fiscal year. Versioned (D3)."""

    class Status(models.TextChoices):
        DRAFT = "draft"
        SUBMITTED = "submitted"
        APPROVED = "approved"
        SUPERSEDED = "superseded"

    office = models.ForeignKey("structure.Office", on_delete=models.PROTECT, related_name="plans")
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="plans")
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    approved_budget = models.DecimalField(null=True, blank=True, **MONEY)
    submitted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    audit_exclude = frozenset({"updated_at"})

    class Meta:
        db_table = "plan"
        ordering = ["fiscal_year", "office", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["office", "fiscal_year", "version"], name="plan_office_fy_version"
            ),
            models.UniqueConstraint(
                fields=["office", "fiscal_year"],
                condition=models.Q(status="approved"),
                name="plan_one_approved_per_office_fy",
            ),
            models.UniqueConstraint(
                fields=["office", "fiscal_year"],
                condition=models.Q(status__in=["draft", "submitted"]),
                name="plan_one_open_version_per_office_fy",
            ),
        ]
        indexes = [models.Index(fields=["agency", "fiscal_year", "status"], name="plan_agency_fy_status")]

    def __str__(self) -> str:
        return f"{self.office.code} {self.fiscal_year.label} v{self.version}"


class Activity(TenantModel):
    """A plan line: an outline heading or a scoreable activity (``row_kind = activity``)."""

    class RowKind(models.TextChoices):
        OUTCOME = "outcome"
        OUTCOME_INDICATOR = "outcome_indicator"
        OUTPUT = "output"
        OUTPUT_INDICATOR = "output_indicator"
        PROGRAM = "program"
        PROJECT = "project"
        ACTIVITY = "activity"

    class Measure(models.TextChoices):
        QUANTITY = "quantity"
        MONEY = "money"
        RECURRING = "recurring"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="rows")
    lineage_id = models.UUIDField(default=uuid.uuid4)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    row_kind = models.CharField(max_length=20, choices=RowKind.choices)
    code = models.CharField(max_length=40, blank=True)
    title = models.TextField()
    sort_order = models.IntegerField(default=0)
    # Activity rows only:
    measure_type = models.CharField(max_length=12, choices=Measure.choices, null=True, blank=True)
    unit = models.CharField(max_length=60, blank=True)
    annual_target = models.DecimalField(null=True, blank=True, **QTY)
    unit_cost = models.DecimalField(null=True, blank=True, **MONEY)
    total_cost = models.DecimalField(null=True, blank=True, **MONEY)
    manual_weight = models.DecimalField(null=True, blank=True, **RATIO)
    implementing_office = models.ForeignKey(
        "structure.Office",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="implemented_activities",
    )

    class Meta:
        db_table = "activity"
        ordering = ["plan", "sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "lineage_id"], name="activity_plan_lineage"),
        ]
        indexes = [
            models.Index(fields=["agency", "implementing_office"], name="activity_agency_impl"),
            models.Index(fields=["agency", "lineage_id"], name="activity_agency_lineage"),
        ]

    @property
    def audit_office_id(self):
        return self.plan.office_id if self.plan_id else None

    @property
    def is_scoreable(self) -> bool:
        return self.row_kind == self.RowKind.ACTIVITY


class ActivityTarget(TenantModel):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="targets")
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT, related_name="+")
    planned_qty = models.DecimalField(default=Decimal("0"), **QTY)
    planned_amount = models.DecimalField(null=True, blank=True, **MONEY)

    class Meta:
        db_table = "activity_target"
        constraints = [models.UniqueConstraint(fields=["activity", "period"], name="activity_target_unique")]


class Indicator(TenantModel):
    class Kind(models.TextChoices):
        OUTCOME = "outcome"
        OUTPUT = "output"

    class Aggregation(models.TextChoices):
        SUM = "sum"
        LAST = "last"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="indicators")
    lineage_id = models.UUIDField(default=uuid.uuid4)
    code = models.CharField(max_length=40, blank=True)
    name = models.TextField()
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.OUTPUT)
    unit = models.CharField(max_length=60, blank=True)
    annual_target = models.DecimalField(default=Decimal("0"), **QTY)
    weight = models.DecimalField(null=True, blank=True, **RATIO)
    aggregation = models.CharField(max_length=6, choices=Aggregation.choices, default=Aggregation.SUM)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "indicator"
        ordering = ["plan", "sort_order"]
        constraints = [models.UniqueConstraint(fields=["plan", "lineage_id"], name="indicator_plan_lineage")]

    @property
    def audit_office_id(self):
        return self.plan.office_id if self.plan_id else None


class IndicatorTarget(TenantModel):
    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE, related_name="targets")
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT, related_name="+")
    planned_value = models.DecimalField(default=Decimal("0"), **QTY)

    class Meta:
        db_table = "indicator_target"
        constraints = [
            models.UniqueConstraint(fields=["indicator", "period"], name="indicator_target_unique")
        ]
