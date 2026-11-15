from config.env import env_bool

from .base import *  # noqa: F403

DEBUG = env_bool("DEBUG", True)
EMAIL_ENABLED = EMAIL_ENABLED  # noqa: F405 — unchanged; set EMAIL_URL=console:// to print mail
