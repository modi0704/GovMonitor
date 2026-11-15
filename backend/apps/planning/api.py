"""Fiscal years and scoring profiles API (MASTERPLAN 13: fiscal-years, scoring-profiles; P5.2)."""

import datetime

from django.http import Http404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import ReadOrAgencyAdmin
from apps.audit.services import jsonable
from apps.planning import services
from apps.planning.models import FiscalYear, ScoringProfile
from apps.scoring import presets


def planning_error(err: services.PlanningError, http=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"detail": err.message, "code": err.code, **err.extra}, status=http)


def period_payload(p) -> dict:
    return {
        "id": str(p.id),
        "month_index": p.month_index,
        "start_date": p.start_date.isoformat(),
        "end_date": p.end_date.isoformat(),
        "cutoff_at": p.cutoff_at.isoformat(),
        "status": p.status,
        "locked_at": p.locked_at.isoformat() if p.locked_at else None,
    }


def profile_payload(profile: ScoringProfile) -> dict:
    data = {f: jsonable(getattr(profile, f)) for f in services.PROFILE_EDITABLE}
    data.update(id=str(profile.id), fiscal_year_id=str(profile.fiscal_year_id), version=profile.version)
    data["locked_months"] = profile.fiscal_year.periods.filter(status="locked").count()
    return data


def fiscal_year_payload(fy: FiscalYear, with_periods: bool = False) -> dict:
    data = {
        "id": str(fy.id),
        "label": fy.label,
        "start_date": fy.start_date.isoformat(),
        "end_date": fy.end_date.isoformat(),
        "status": fy.status,
        "preset": fy.profile.preset,
        "profile_id": str(fy.profile.id),
    }
    if with_periods:
        data["periods"] = [period_payload(p) for p in fy.periods.order_by("month_index")]
    return data


def get_fy(fy_id) -> FiscalYear:
    fy = FiscalYear.objects.select_related("profile").filter(pk=fy_id).first()
    if fy is None:
        raise Http404()
    return fy


class FiscalYearCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=40)
    start_year = serializers.IntegerField(min_value=2000, max_value=2100)
    preset = serializers.ChoiceField(choices=sorted(presets.PRESETS), default=presets.DEFAULT_PRESET)


class FiscalYearListView(APIView):
    permission_classes = [ReadOrAgencyAdmin]

    def get(self, request):
        years = FiscalYear.objects.select_related("profile").order_by("-start_date")
        return Response([fiscal_year_payload(fy) for fy in years])

    def post(self, request):
        s = FiscalYearCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            fy = services.create_fiscal_year(d["label"], d["start_year"], d["preset"])
        except services.PlanningError as err:
            return planning_error(err)
        return Response(fiscal_year_payload(fy, with_periods=True), status=status.HTTP_201_CREATED)


class FiscalYearDetailView(APIView):
    permission_classes = [ReadOrAgencyAdmin]

    def get(self, request, fy_id):
        return Response(fiscal_year_payload(get_fy(fy_id), with_periods=True))

    def patch(self, request, fy_id):
        fy = get_fy(fy_id)
        if "status" in request.data:
            try:
                services.set_fiscal_year_status(fy, str(request.data["status"]))
            except services.PlanningError as err:
                return planning_error(err)
        return Response(fiscal_year_payload(fy, with_periods=True))


class PresetListView(APIView):
    def get(self, request):
        return Response(
            [
                {
                    "name": name,
                    "description": presets.PRESET_DESCRIPTIONS.get(name, ""),
                    "settings": jsonable(settings),
                }
                for name, settings in presets.PRESETS.items()
            ]
        )


class ScoringProfileView(APIView):
    permission_classes = [ReadOrAgencyAdmin]

    def _get(self, profile_id) -> ScoringProfile:
        profile = ScoringProfile.objects.select_related("fiscal_year").filter(pk=profile_id).first()
        if profile is None:
            raise Http404()
        return profile

    def get(self, request, profile_id):
        return Response(profile_payload(self._get(profile_id)))

    def patch(self, request, profile_id):
        profile = self._get(profile_id)
        changes = {k: v for k, v in request.data.items() if k != "confirm"}
        try:
            services.update_profile(profile, changes, confirm=bool(request.data.get("confirm")))
        except services.PlanningError as err:
            return planning_error(err, http=409 if err.code == "confirm_required" else 400)
        profile.refresh_from_db()
        return Response(profile_payload(profile))


class PeriodDetailView(APIView):
    """PATCH ``{"cutoff_at": ISO datetime}`` — move one month's cutoff (P7.2). Open months only."""

    permission_classes = [ReadOrAgencyAdmin]

    def _get(self, period_id):
        from apps.planning.models import ReportingPeriod

        period = ReportingPeriod.objects.select_related("fiscal_year").filter(pk=period_id).first()
        if period is None:
            raise Http404()
        return period

    def get(self, request, period_id):
        return Response(period_payload(self._get(period_id)))

    def patch(self, request, period_id):
        from django.utils.dateparse import parse_datetime

        period = self._get(period_id)
        if period.status == "locked":
            return Response(
                {"detail": "A locked month keeps its cutoff.", "code": "period_locked"}, status=409
            )
        value = parse_datetime(str(request.data.get("cutoff_at", "")))
        if value is None or value.tzinfo is None:
            return Response({"cutoff_at": ["Give a date and time with a time zone."]}, status=400)
        if value.date() < period.end_date:
            return Response({"cutoff_at": ["The cutoff cannot be before the month ends."]}, status=400)
        period.cutoff_at = value.astimezone(datetime.UTC)  # stored in UTC (5.4 conventions)
        period.save(update_fields=["cutoff_at"])
        return Response(period_payload(period))
