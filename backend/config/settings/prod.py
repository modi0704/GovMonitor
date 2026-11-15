from config.env import env, env_bool, env_int

from .base import *  # noqa: F403

DEBUG = False
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
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000 if _secure else 0)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
LOG_LEVEL = env("LOG_LEVEL", "INFO")
