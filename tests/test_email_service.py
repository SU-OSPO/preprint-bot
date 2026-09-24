import sys
import types
import importlib
import pytest

MODULE = "services.email_service"


@pytest.fixture
def email_service(monkeypatch):
    """Fixture to reload email_service with fresh config mocking safely."""
    config_mock = types.ModuleType("config")
    config_mock.EMAIL_HOST = "smtp.test.com"
    config_mock.EMAIL_PORT = 587
    config_mock.EMAIL_USER = "user"
    config_mock.EMAIL_PASSWORD = "password"
    config_mock.EMAIL_FROM_ADDRESS = "from@test.com"
    config_mock.EMAIL_FROM_NAME = "Test"
    config_mock.SITE_URL = "https://example.com"
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


def test_recommendations_url_configuration(email_service):
    assert email_service.RECOMMENDATIONS_URL.endswith("/recommendations/")


def test_digest_email_links(email_service):
    papers = [
        {
            "source_id": "2301.00001",
            "title": "Test Paper Title",
            "authors": ["Author One"],
            "summary_text": "This is a test summary. It has multiple sentences so that the Read More link gets triggered properly in the template rendering logic.",
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
    assert email_service.RECOMMENDATIONS_URL in html
