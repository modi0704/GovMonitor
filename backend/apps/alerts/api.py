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
