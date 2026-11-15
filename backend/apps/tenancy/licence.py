"""Office-install licence (P13.5, D13).

A licence file is JSON: ``{"payload": {...}, "signature": "<base64 Ed25519>"}``, the signature
covering the payload serialised with sorted keys and no spaces. The payload names the agency, the
expiry date and the seat limit. Only the vendor's public key ships in the image; licences are
signed with ``tools/licence.py`` and the vendor's private key.

Rules (single-agency installs only; ``multi`` mode never needs a licence):
* 30 days before expiry everyone sees a banner;
* with no valid licence (missing, damaged, expired) the system is READ-ONLY — people can still
  sign in, read everything and export it, so no one is ever locked out of their data;
* above the seat limit no new user can be added (existing users keep working).
"""

import base64
import datetime
import json
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.conf import settings
from django.utils import timezone

WARN_DAYS = 30
PUBLIC_KEY_FILE = Path(__file__).with_name("licence_public_key.txt")

# Writes allowed without a valid licence: signing in and out, one's own password and two-step
# settings, marking notifications read, and getting data out (exports).
READ_ONLY_ALLOWED = (
    "/api/v1/auth/",
    "/api/v1/notifications/",
    "/api/v1/exports/",
    "/platform/api/",
)


@dataclass(frozen=True)
class LicenceState:
    status: str  # not_required | missing | invalid | valid | expiring | expired
    agency: str = ""
    expires: datetime.date | None = None
    seats: int | None = None
    message: str = ""

    @property
    def read_only(self) -> bool:
        return self.status in ("missing", "invalid", "expired")

    @property
    def days_left(self) -> int | None:
        if self.expires is None:
            return None
        return (self.expires - today()).days


def today() -> datetime.date:
    return timezone.localdate()


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def public_key() -> Ed25519PublicKey:
    text = getattr(settings, "LICENCE_PUBLIC_KEY", "") or next(
        line.strip()
        for line in PUBLIC_KEY_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    )
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(text))


def verify(raw: str) -> dict:
    """The payload of a genuine licence; raises ValueError for anything else."""
    try:
        doc = json.loads(raw)
        payload, signature = doc["payload"], base64.b64decode(doc["signature"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("The licence file cannot be read.") from exc
    try:
        public_key().verify(signature, canonical(payload))
    except InvalidSignature as exc:
        raise ValueError("The licence file is not genuine (signature does not match).") from exc
    return payload


_cache: dict = {}


def state() -> LicenceState:
    """The licence situation now. Cached per file content and day."""
    if settings.DEPLOYMENT_MODE != "single":
        return LicenceState("not_required")
    path = getattr(settings, "LICENCE_FILE", "")
    if not path or not Path(path).is_file():
        return LicenceState("missing", message="No licence is installed: the system is read-only.")
    raw = Path(path).read_text(encoding="utf-8")
    key = (raw, today())
    if key in _cache:
        return _cache[key]
    try:
        payload = verify(raw)
        expires = datetime.date.fromisoformat(payload["expires"])
        seats = int(payload["seats"])
        agency = str(payload.get("agency", ""))
    except (ValueError, KeyError, TypeError) as exc:
        result = LicenceState("invalid", message=f"{exc} The system is read-only.")
    else:
        left = (expires - today()).days
        if left < 0:
            status, message = (
                "expired",
                f"The licence expired on {expires:%d %B %Y}: the system is read-only.",
            )
        elif left <= WARN_DAYS:
            status, message = "expiring", f"The licence expires on {expires:%d %B %Y} ({left} days left)."
        else:
            status, message = "valid", ""
        result = LicenceState(status, agency, expires, seats, message)
    _cache.clear()
    _cache[key] = result
    return result


def payload(user_count: int | None = None) -> dict:
    s = state()
    return {
        "status": s.status,
        "read_only": s.read_only,
        "agency": s.agency,
        "expires": s.expires.isoformat() if s.expires else None,
        "days_left": s.days_left,
        "seats": s.seats,
        "seats_used": user_count,
        "message": s.message,
    }


def seats_available(active_users: int) -> bool:
    s = state()
    return s.status == "not_required" or s.seats is None or active_users < s.seats


class LicenceMiddleware:
    """Without a valid licence (single mode), refuse changes but never reading or exporting."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        writes = request.method not in ("GET", "HEAD", "OPTIONS") and request.path.startswith("/api/")
        if writes and not request.path.startswith(READ_ONLY_ALLOWED):
            s = state()
            if s.read_only:
                from django.http import JsonResponse

                return JsonResponse({"detail": s.message, "code": "licence_read_only"}, status=403)
        return self.get_response(request)
