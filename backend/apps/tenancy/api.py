"""Support grants, agency side (P1.7): the agency administrator lets one platform admin read the
agency's data for a limited time. Without an unexpired, unrevoked grant the platform area shows
no agency data."""

import zoneinfo
from datetime import timedelta

from django.db import connection
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAgencyAdmin, ReadOrAgencyAdmin
from apps.tenancy.models import Agency, SupportGrant

MAX_GRANT_HOURS = 24 * 14


def _platform_admin_id(email: str):
    with connection.cursor() as cur:
        cur.execute("SELECT platform_admin_lookup(%s)", [email])
        return cur.fetchone()[0]


def _emails(ids) -> dict:
    if not ids:
        return {}
    with connection.cursor() as cur:
        cur.execute("SELECT id, email FROM platform_admin_emails(%s::uuid[])", [[str(i) for i in ids]])
        return dict(cur.fetchall())


def grant_payload(grant: SupportGrant, emails: dict) -> dict:
    now = timezone.now()
    return {
        "id": str(grant.id),
        "platform_admin_email": emails.get(grant.platform_admin_id),
        "granted_by": grant.granted_by.email,
        "reason": grant.reason,
        "created_at": grant.created_at.isoformat(),
        "expires_at": grant.expires_at.isoformat(),
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        "active": grant.revoked_at is None and grant.expires_at > now,
    }


class GrantCreateSerializer(serializers.Serializer):
    platform_admin_email = serializers.EmailField()
    hours = serializers.IntegerField(min_value=1, max_value=MAX_GRANT_HOURS)
    reason = serializers.CharField(max_length=2000)


class SupportGrantListView(APIView):
    permission_classes = [IsAgencyAdmin]

    def get(self, request):
        grants = list(SupportGrant.objects.select_related("granted_by").order_by("-created_at"))
        emails = _emails({g.platform_admin_id for g in grants})
        return Response([grant_payload(g, emails) for g in grants])

    def post(self, request):
        s = GrantCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        admin_id = _platform_admin_id(d["platform_admin_email"])
        if admin_id is None:
            return Response(
                {"platform_admin_email": ["No active vendor support account has this email."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        grant = SupportGrant.objects.create(
            platform_admin_id=admin_id,
            granted_by=request.user,
            expires_at=timezone.now() + timedelta(hours=d["hours"]),
            reason=d["reason"],
        )
        return Response(grant_payload(grant, _emails([admin_id])), status=status.HTTP_201_CREATED)


class SupportGrantRevokeView(APIView):
    permission_classes = [IsAgencyAdmin]

    def delete(self, request, grant_id):
        grant = SupportGrant.objects.select_related("granted_by").filter(pk=grant_id).first()
        if grant is None:
            raise Http404()
        if grant.revoked_at is None:
            grant.revoked_at = timezone.now()
            grant.save(update_fields=["revoked_at"])
        return Response(grant_payload(grant, _emails([grant.platform_admin_id])))


# ---- The signed-in user's agency (P2.7) ----------------------------------------------------------


def agency_payload(agency: Agency) -> dict:
    return {
        "id": str(agency.id),
        "name": agency.name,
        "code": agency.code,
        "timezone": agency.timezone,
        "fiscal_year_start_month": agency.fiscal_year_start_month,
        "setup_complete": bool(agency.settings.get("setup_complete")),
        "settings": agency.settings,
    }


class AgencyView(APIView):
    """GET the agency; PATCH name / timezone / setup_complete (agency administrator)."""

    permission_classes = [ReadOrAgencyAdmin]

    def get(self, request):
        return Response(agency_payload(Agency.objects.get(pk=request.user.agency_id)))

    def patch(self, request):
        agency = Agency.objects.get(pk=request.user.agency_id)
        fields = []
        if "name" in request.data:
            name = str(request.data["name"]).strip()
            if not name:
                return Response({"name": ["The agency needs a name."]}, status=400)
            agency.name = name[:200]
            fields.append("name")
        if "timezone" in request.data:
            tz = str(request.data["timezone"])
            if tz not in zoneinfo.available_timezones():
                return Response({"timezone": ["Unknown time zone."]}, status=400)
            agency.timezone = tz
            fields.append("timezone")
        if "setup_complete" in request.data:
            agency.settings = {**agency.settings, "setup_complete": bool(request.data["setup_complete"])}
            fields.append("settings")
        if fields:
            agency.save(update_fields=fields)
        return Response(agency_payload(agency))
