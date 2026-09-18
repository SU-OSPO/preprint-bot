"""
Custom context processor that injects commonly needed values into every template.
"""

from datetime import date, timedelta

from django.conf import settings as django_settings


def date_helpers(request):
    """Inject today / week_ago / month_ago for quick-filter buttons."""
    today = date.today()
    return {
        "today": today.isoformat(),
        "week_ago": (today - timedelta(days=7)).isoformat(),
        "month_ago": (today - timedelta(days=30)).isoformat(),
    }


def site_settings(request):
    """Expose selected settings to every template."""
    return {
        "SUPPORT_EMAIL": getattr(django_settings, "SUPPORT_EMAIL", "support@example.com"),
        "SITE_NAME": getattr(django_settings, "SITE_NAME", "Preprint Bot"),
        "SHOW_BETA_BANNER": getattr(django_settings, "SHOW_BETA_BANNER", True),
        "ORCID_ENABLED": bool(getattr(django_settings, "ORCID_CLIENT_ID", "")),
        "ORCID_BASE_URL": "https://sandbox.orcid.org" if getattr(django_settings, "ORCID_SANDBOX", False) else "https://orcid.org",
        "ACCENT_COLOR": getattr(django_settings, "ACCENT_COLOR", ""),
        "NAV_COLOR": getattr(django_settings, "NAV_COLOR", ""),
        "REGISTRATION_OPEN": getattr(django_settings, "REGISTRATION_OPEN", True),
        "SCRIPT_PREFIX": getattr(django_settings, "FORCE_SCRIPT_NAME", "") or "",
        "FONT_FAMILY": getattr(django_settings, "FONT_FAMILY", ""),
    }
