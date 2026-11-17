from config.env import env, env_bool, env_int

from .base import *  # noqa: F403

DEBUG = False
# Demo seeding is a development/test tool and is not registered in the shipped app.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "seed"]  # noqa: F405
if SECRET_KEY.startswith("insecure-"):  # noqa: F405
    raise RuntimeError("Set SECRET_KEY for production")

for _var in ("DATABASE_URL", "DATABASE_ADMIN_URL"):
    if not env(_var):
        raise RuntimeError(f"Set {_var} for production")

# Behind a TLS-terminating proxy (Caddy) set SECURE_SSL=1.
_secure = env_bool("SECURE_SSL", False)
SESSION_COOKIE_SECURE = _secure
CSRF_COOKIE_SECURE = _secure
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if _secure else None
# HSTS only when the site is really served over TLS (never on a plain-HTTP office install).
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000 if _secure else 0) if _secure else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
LOG_LEVEL = env("LOG_LEVEL", "INFO")
# Structured logs by default in production; LOG_FORMAT=plain for reading by eye.
LOG_FORMAT = env("LOG_FORMAT", "json")
LOGGING["handlers"]["console"]["formatter"] = "json" if LOG_FORMAT == "json" else "plain"  # noqa: F405
