"""Email delivery of notifications (P11.4, D16).

Only when the server has email (``EMAIL_URL``) and the agency turned it on (``email_enabled``).
Plain, short messages with links; users who opted out get none; at most one digest per user per
local day. Without SMTP nothing is sent and nothing fails: notifications stay in the app.
"""

import datetime
import logging
from collections import defaultdict

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.alerts.models import Notification
from apps.alerts.rules import current as current_rule

log = logging.getLogger(__name__)
LOOKBACK_DAYS = 7  # older unsent notifications are not emailed any more
MAX_ITEMS = 20


def absolute(link: str) -> str:
    base = (getattr(settings, "PUBLIC_URL", "") or "").rstrip("/")
    return f"{base}{link}" if base and link.startswith("/") else link


def digest_text(user, items) -> tuple[str, str]:
    subject = f"GovMonitor: {len(items)} new alert{'s' if len(items) != 1 else ''}"
    lines = [f"Hello {user.full_name or user.email},", "", "New in GovMonitor:", ""]
    for n in items[:MAX_ITEMS]:
        lines.append(f"- {n.title}")
        if n.link:
            lines.append(f"  {absolute(n.link)}")
    if len(items) > MAX_ITEMS:
        lines.append(f"... and {len(items) - MAX_ITEMS} more in the app.")
    lines += [
        "",
        "To stop these emails, click your name at the top of GovMonitor and untick the email option.",
    ]
    return subject, "\n".join(lines)


def send_digests(now=None) -> int:
    """Email each user one digest of their unsent, unread notifications. Returns emails sent."""
    from apps.alerts.services import _tz
    from apps.tenancy import context

    if not settings.EMAIL_ENABLED or not current_rule().email_enabled:
        return 0
    now = now or timezone.now()
    tz = _tz(context.require_agency_id())
    local = now.astimezone(tz)
    start_of_day = datetime.datetime.combine(local.date(), datetime.time.min, tzinfo=tz)
    already = set(
        Notification.objects.filter(emailed_at__gte=start_of_day).values_list("user_id", flat=True).distinct()
    )
    pending = (
        Notification.objects.select_related("user")
        .filter(
            emailed_at=None,
            read_at=None,
            created_at__gte=now - datetime.timedelta(days=LOOKBACK_DAYS),
            user__is_active=True,
            user__email_opt_out=False,
        )
        .exclude(user_id__in=already)
        .order_by("created_at")
    )
    per_user = defaultdict(list)
    for n in pending:
        per_user[n.user].append(n)
    sent = 0
    for user, items in per_user.items():
        subject, body = digest_text(user, items)
        try:
            send_mail(subject, body, None, [user.email], fail_silently=False)
        except Exception:  # noqa: BLE001 — one bad address or SMTP hiccup must not stop the others
            log.warning("alert digest to %s failed", user.email, exc_info=True)
            continue
        Notification.objects.filter(pk__in=[n.pk for n in items]).update(emailed_at=now)
        sent += 1
    return sent
