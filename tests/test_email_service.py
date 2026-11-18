import re
import sys
import types
import importlib
import pytest

MODULE = "services.email_service"


@pytest.fixture
def email_service(monkeypatch, request):
    """Fixture to reload email_service with fresh config mocking safely."""
    config_mock = types.ModuleType("config")
    config_mock.EMAIL_HOST = "smtp.test.com"
    config_mock.EMAIL_PORT = 587
    config_mock.EMAIL_USER = "user"
    config_mock.EMAIL_PASSWORD = "password"
    config_mock.EMAIL_FROM_ADDRESS = "from@test.com"
    config_mock.EMAIL_FROM_NAME = "Test"
    # Indirect parametrization overrides SITE_URL; default has no trailing slash
    config_mock.SITE_URL = getattr(request, "param", "https://example.com")
    config_mock.ADMIN_EMAIL = "admin@example.com"

    monkeypatch.setitem(sys.modules, "config", config_mock)

    cached = sys.modules.pop(MODULE, None)
    try:
        yield importlib.import_module(MODULE)
    finally:
        if cached is not None:
            sys.modules[MODULE] = cached
            if hasattr(sys.modules.get("services"), "email_service"):
                setattr(sys.modules["services"], "email_service", cached)
        else:
            sys.modules.pop(MODULE, None)
            if hasattr(sys.modules.get("services"), "email_service"):
                delattr(sys.modules["services"], "email_service")


@pytest.mark.parametrize(
    "email_service", ["https://example.com", "https://example.com/"], indirect=True
)
def test_recommendations_url_configuration(email_service):
    assert email_service.RECOMMENDATIONS_URL == "https://example.com/recommendations/"


def test_digest_email_links(email_service):
    papers = [
        {
            "source_id": "2301.00001",
            "source": "arxiv",
            "title": "Test Paper Title",
            "authors": ["Author One"],
            # Four sentences, so the summary truncates and "Read more" renders
            "summary_text": "One. Two. Three. Four.",
        }
    ]
    html = email_service.build_digest_html(
        profile_name="Test Profile",
        papers=papers,
        run_date="2026-09-04",
        shown=1,
        total=1,
        frequency="daily",
    )
    # Header logo, "Read more" link, and the call-to-action button
    url = re.escape(email_service.RECOMMENDATIONS_URL)
    for anchor in ("Preprint Bot", "Read more →", "See all recommendations →"):
        assert re.search(rf'href="{url}"[^>]*>{re.escape(anchor)}<', html)

    # Paper titles still link to the source landing page, not the digest URL
    assert 'href="https://arxiv.org/abs/2301.00001"' in html
