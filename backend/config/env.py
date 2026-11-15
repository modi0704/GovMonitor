"""Environment-variable helpers (MASTERPLAN 5.4). No third-party dependency."""

import os
from urllib.parse import parse_qs, unquote, urlparse


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None or value == "" else int(value)


def env_list(name: str, default: str = "") -> list[str]:
    raw = env(name, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_email_url(url: str | None) -> dict:
    """Parse ``smtp://user:pass@host:port?tls=1&ssl=0&from=noreply@x`` into Django settings.

    An empty URL means email is disabled (MASTERPLAN D16).
    """
    if not url:
        return {"EMAIL_ENABLED": False, "EMAIL_BACKEND": "django.core.mail.backends.dummy.EmailBackend"}
    parts = urlparse(url)
    query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
    if parts.scheme in {"console", "consolemail"}:
        backend = "django.core.mail.backends.console.EmailBackend"
    elif parts.scheme in {"locmem", "memory"}:
        backend = "django.core.mail.backends.locmem.EmailBackend"
    elif parts.scheme in {"smtp", "smtps", "submission"}:
        backend = "django.core.mail.backends.smtp.EmailBackend"
    else:
        raise ValueError(f"Unsupported EMAIL_URL scheme: {parts.scheme!r}")
    use_ssl = parts.scheme == "smtps" or query.get("ssl") in {"1", "true"}
    use_tls = parts.scheme == "submission" or query.get("tls") in {"1", "true"}
    return {
        "EMAIL_ENABLED": True,
        "EMAIL_BACKEND": backend,
        "EMAIL_HOST": parts.hostname or "localhost",
        "EMAIL_PORT": parts.port or (465 if use_ssl else 587 if use_tls else 25),
        "EMAIL_HOST_USER": unquote(parts.username or ""),
        "EMAIL_HOST_PASSWORD": unquote(parts.password or ""),
        "EMAIL_USE_SSL": use_ssl,
        "EMAIL_USE_TLS": use_tls and not use_ssl,
        "DEFAULT_FROM_EMAIL": query.get("from", "noreply@localhost"),
    }
