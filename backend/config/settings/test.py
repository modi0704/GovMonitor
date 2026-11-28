from .base import *  # noqa: F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast hashing in tests only
STORAGES = {  # noqa: F405
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Tests never serve static files; WhiteNoise would warn about the missing STATIC_ROOT.
MIDDLEWARE = [m for m in MIDDLEWARE if m != "whitenoise.middleware.WhiteNoiseMiddleware"]  # noqa: F405
WHITENOISE_ROOT = None
AUDIT_ROWS_HEADER = True  # lets P3.4 count the audit rows each request wrote

# The test suite runs with every switchable feature ON, so the kept code (sign-in, licence, platform
# area, alerts, automatic closing) stays tested; tests of the shipped defaults switch them off (D49).
LOGIN_DISABLED = False
LICENCE_ENFORCED = True
PLATFORM_ENABLED = True
ALERTS_ENABLED = True
AUTO_LOCK_ENABLED = True
OFFICE_GROUPS_ENABLED = True
