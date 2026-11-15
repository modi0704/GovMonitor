"""Alerts API (P11.1, P11.3): the agency's alert rule and each user's notifications."""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAgencyAdmin
from apps.alerts import rules


class AlertRuleView(APIView):
    """GET / PATCH ``{remind_days_before: [5, 1], delay_threshold: "0.05", email_enabled}``."""

    permission_classes = [IsAgencyAdmin]

    def get(self, request):
        return Response(rules.payload(rules.current()))

    def patch(self, request):
        try:
            rule = rules.update(request.data)
        except rules.RuleError as err:
            return Response({err.field: [err.message]}, status=400)
        return Response(rules.payload(rule))


def notification_payload(n) -> dict:
    return {
        "id": str(n.id),
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "created_at": n.created_at.isoformat(),
        "read_at": n.read_at.isoformat() if n.read_at else None,
    }


def _mine(request):
    from apps.alerts.models import Notification

    return Notification.objects.filter(user=request.user)


class NotificationListView(APIView):
    """GET ``?unread=1&limit=50`` — the signed-in user's notifications, newest first."""

    def get(self, request):
        qs = _mine(request)
        if request.query_params.get("unread") in ("1", "true"):
            qs = qs.filter(read_at=None)
        try:
            limit = max(1, min(int(request.query_params.get("limit", 50)), 200))
        except ValueError:
            limit = 50
        rows = list(qs.order_by("-created_at")[:limit])
        return Response(
            {
                "results": [notification_payload(n) for n in rows],
                "unread": _mine(request).filter(read_at=None).count(),
            }
        )


class UnreadCountView(APIView):
    def get(self, request):
        return Response({"unread": _mine(request).filter(read_at=None).count()})


class NotificationReadView(APIView):
    """POST — mark one notification read (not audited: it changes only the reader's own inbox)."""

    def post(self, request, notification_id):
        from django.http import Http404
        from django.utils import timezone

        n = _mine(request).filter(pk=notification_id).first()
        if n is None:
            raise Http404()
        if n.read_at is None:
            _mine(request).filter(pk=n.pk).update(read_at=timezone.now())
        return Response({"unread": _mine(request).filter(read_at=None).count()})


class NotificationReadAllView(APIView):
    def post(self, request):
        from django.utils import timezone

        _mine(request).filter(read_at=None).update(read_at=timezone.now())
        return Response({"unread": 0})
