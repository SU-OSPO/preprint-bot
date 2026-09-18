"""
Django settings for preprint_bot_web project.

Connects to the same PostgreSQL database used by the FastAPI backend.
Models are fully managed by Django — migrations create and alter tables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

_INSECURE_KEY = "django-insecure-change-me-in-production-abc123xyz"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", _INSECURE_KEY)

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

if not DEBUG and SECRET_KEY == _INSECURE_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set to a unique, unpredictable value in production. "
        "Generate one with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "preprint_bot_web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.date_helpers",
                "core.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "preprint_bot_web.wsgi.application"

# ---------------------------------------------------------------------------
# Database – points at the existing preprint_bot PostgreSQL database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DATABASE_NAME", "preprint_bot"),
        "USER": os.getenv("DATABASE_USER", "postgres"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", ""),
        "HOST": os.getenv("DATABASE_HOST", "localhost"),
        "PORT": os.getenv("DATABASE_PORT", "5432"),
    }
}

# ---------------------------------------------------------------------------
# Authentication — uses PBUser (email-based login via ModelBackend)
# ---------------------------------------------------------------------------

# Where Django auth redirects (named URLs so FORCE_SCRIPT_NAME is respected)
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# ---------------------------------------------------------------------------
# Password validation (enforced in registration, password reset, and admin)
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / Media files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# PDF storage paths (mirrors FastAPI config)
PDF_DATA_DIR = Path(os.getenv("PDF_DATA_DIR", BASE_DIR.parent / "pdf_data"))
USER_PDF_DIR = PDF_DATA_DIR / "user_pdfs"          # legacy — used by FastAPI pipeline only
USER_PROCESSED_DIR = PDF_DATA_DIR / "user_processed"  # legacy — used by FastAPI pipeline only
PAPER_STORAGE_DIR = PDF_DATA_DIR / "papers"  # hash-based deduplicated storage

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Use our custom user model for Django's auth system
AUTH_USER_MODEL = "core.PBUser"

# ---------------------------------------------------------------------------
# FastAPI backend URL (used for operations that still hit the API)
# ---------------------------------------------------------------------------

FASTAPI_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Site-specific settings
# ---------------------------------------------------------------------------

SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@example.com")
SITE_NAME = os.getenv("SITE_NAME", "Preprint Bot")
SHOW_BETA_BANNER = os.getenv("SHOW_BETA_BANNER", "True").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Optional font-family override; empty keeps the default font
# ---------------------------------------------------------------------------
FONT_FAMILY = ""

# ---------------------------------------------------------------------------
# arXiv search settings
# ---------------------------------------------------------------------------

ARXIV_SEARCH_MAX_RESULTS = int(os.getenv("ARXIV_SEARCH_MAX_RESULTS", 500))
ARXIV_SEARCH_PER_PAGE = int(os.getenv("ARXIV_SEARCH_PER_PAGE", 50))
ACCENT_COLOR = os.getenv("ACCENT_COLOR", "")  # e.g. "#e65100" — overrides the default blue
NAV_COLOR = os.getenv("NAV_COLOR", "")  # e.g. "#1b5e20" — overrides the dark navbar
REGISTRATION_OPEN = os.getenv("REGISTRATION_OPEN", "True").lower() in ("true", "1", "yes")
REQUIRE_EMAIL_VERIFICATION = os.getenv("REQUIRE_EMAIL_VERIFICATION", "False").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# ORCID OAuth2 (optional — leave ORCID_CLIENT_ID blank to disable)
# Register at https://orcid.org/developer-tools
# ---------------------------------------------------------------------------

ORCID_CLIENT_ID = os.getenv("ORCID_CLIENT_ID", "")
ORCID_CLIENT_SECRET = os.getenv("ORCID_CLIENT_SECRET", "")
ORCID_SANDBOX = os.getenv("ORCID_SANDBOX", "False").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Email backend — reads the same env vars as the FastAPI email_service.
# If EMAIL_HOST is set, use SMTP; otherwise fall back to console (dev).
# ---------------------------------------------------------------------------

if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    EMAIL_HOST_USER = os.getenv("EMAIL_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    _from_name = os.getenv("EMAIL_FROM_NAME", SITE_NAME)
    _from_addr = os.getenv("EMAIL_FROM_ADDRESS", f"noreply@{os.getenv('SITE_DOMAIN', 'localhost')}")
    DEFAULT_FROM_EMAIL = f"{_from_name} <{_from_addr}>"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"noreply@{os.getenv('SITE_DOMAIN', 'localhost')}")

# ---------------------------------------------------------------------------
# Local overrides (not committed to version control)
# ---------------------------------------------------------------------------
# Create preprint_bot_web/local_settings.py to override any setting above.
# See local_settings.py.example for a template.

try:
    from .local_settings import *  # noqa: F401, F403
except ImportError:
    pass
