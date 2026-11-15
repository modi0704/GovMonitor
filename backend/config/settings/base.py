"""Base settings shared by dev, test and prod. Every value comes from the environment (MASTERPLAN 5.4)."""

from pathlib import Path

import dj_database_url

from config.env import env, env_bool, env_int, env_list, parse_email_url

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = BACKEND_DIR.parent
FRONTEND_DIST = Path(env("FRONTEND_DIST", str(REPO_DIR / "frontend" / "dist")))

SECRET_KEY = env("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# --- Product configuration -------------------------------------------------------------------
DEPLOYMENT_MODE = env("DEPLOYMENT_MODE", "multi")
if DEPLOYMENT_MODE not in {"single", "multi"}:
    raise ValueError("DEPLOYMENT_MODE must be 'single' or 'multi'")
SESSION_IDLE_MINUTES = env_int("SESSION_IDLE_MINUTES", 60)
MAX_UPLOAD_MB = env_int("MAX_UPLOAD_MB", 25)
LICENCE_FILE = env("LICENCE_FILE", "")
# Public address of the site (e.g. https://monitor.example.gov), used for links in emails.
PUBLIC_URL = env("PUBLIC_URL", "")
WORKER_HEARTBEAT_STALE_SECONDS = env_int("WORKER_HEARTBEAT_STALE_SECONDS", 120)
# Set when a trusted reverse proxy (Caddy) sets X-Forwarded-For; the audit log then records it.
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", False)

# --- Applications ----------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "apps.tenancy",
    "apps.accounts",
    "apps.structure",
    "apps.audit",
    "apps.scoring",
    "apps.planning",
    "apps.reporting",
    "apps.results",
    "apps.alerts",
    "apps.exports",
    "apps.jobs",
    "seed",
]

MIDDLEWARE = [
    "apps.audit.middleware.AuditContextMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.tenancy.middleware.TenantMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.SessionIdleMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

# --- Database (MASTERPLAN 6.1) ---------------------------------------------------------------
# `default` connects as app_user (subject to row-level security, owns nothing).
# `owner` connects as app_owner (owns the tables, BYPASSRLS): migrations and platform operations.
# Defaults are for local development only; deployments always set both variables.
_DEFAULT_DB = "postgres://app_user:app_user@localhost:5432/govmonitor"
_DEFAULT_ADMIN_DB = "postgres://app_owner:app_owner@localhost:5432/govmonitor"
DATABASES = {
    "default": dj_database_url.parse(env("DATABASE_URL", _DEFAULT_DB), conn_max_age=0),
    "owner": dj_database_url.parse(env("DATABASE_ADMIN_URL", _DEFAULT_ADMIN_DB), conn_max_age=0),
}
# Every request runs in one transaction on `default`. Platform-owner code opens its own
# transactions on `owner` explicitly.
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Authentication --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
SESSION_COOKIE_NAME = "gm_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12  # absolute maximum; idle timeout is SESSION_IDLE_MINUTES
CSRF_COOKIE_NAME = "gm_csrftoken"
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it to send X-CSRFToken
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"

# --- Internationalisation (store UTC; agency timezone applied for display) -------------------
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# --- Static files and the built SPA ----------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BACKEND_DIR / "staticfiles"
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.exists() else None
WHITENOISE_INDEX_FILE = False

# --- File storage (MOVs, logos, export files) ------------------------------------------------
FILE_STORAGE = env("FILE_STORAGE", "local")
FILE_ROOT = Path(env("FILE_ROOT", str(REPO_DIR / "var" / "files")))
if FILE_STORAGE == "s3":
    _default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": env("S3_ENDPOINT"),
            "bucket_name": env("S3_BUCKET"),
            "access_key": env("S3_ACCESS_KEY"),
            "secret_key": env("S3_SECRET_KEY"),
            "default_acl": None,
            "querystring_auth": True,
            "file_overwrite": False,
        },
    }
elif FILE_STORAGE == "local":
    _default_storage = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(FILE_ROOT), "base_url": None},
    }
else:
    raise ValueError("FILE_STORAGE must be 'local' or 's3'")
STORAGES = {
    "default": _default_storage,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --- Email (D16: empty EMAIL_URL = email disabled) -------------------------------------------
_email = parse_email_url(env("EMAIL_URL", ""))
EMAIL_ENABLED = _email.pop("EMAIL_ENABLED")
globals().update(_email)

# --- REST framework --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["apps.accounts.permissions.IsSignedIn"],
    "EXCEPTION_HANDLER": "apps.accounts.api_errors.exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

# --- Logging ---------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}

# The role the app runs as; migrations grant it table privileges (apps/tenancy/db.py).
DB_APP_ROLE = DATABASES["default"]["USER"]
