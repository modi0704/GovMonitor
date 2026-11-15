"""Optional TOTP two-factor authentication (P1.5): enrolment with a QR code, verification at
sign-in, single-use recovery codes."""

import io
import secrets

import pyotp
import qrcode
import qrcode.image.svg
from django.contrib.auth.hashers import check_password, make_password

ISSUER = "GovMonitor"
RECOVERY_CODE_COUNT = 10
SESSION_SETUP_KEY = "_totp_setup_secret"
MAX_2FA_ATTEMPTS = 5


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_svg(data: str) -> str:
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


def verify_code(secret: str, code: str) -> bool:
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def _format(raw: str) -> str:
    return f"{raw[:5]}-{raw[5:]}"


def normalise_recovery_code(code: str) -> str:
    return "".join(ch for ch in (code or "").lower() if ch.isalnum())


def new_recovery_codes() -> tuple[list[str], list[str]]:
    """Return (plain codes to show once, hashes to store)."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    plain = [
        _format("".join(secrets.choice(alphabet) for _ in range(10))) for _ in range(RECOVERY_CODE_COUNT)
    ]
    hashes = [make_password(normalise_recovery_code(c)) for c in plain]
    return plain, hashes


def use_recovery_code(user, code: str) -> bool:
    """Consume a matching recovery code. Caller saves the user."""
    wanted = normalise_recovery_code(code)
    if not wanted:
        return False
    for stored in list(user.recovery_codes or []):
        if check_password(wanted, stored):
            user.recovery_codes = [c for c in user.recovery_codes if c != stored]
            return True
    return False
