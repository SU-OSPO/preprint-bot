import importlib
import sys
import types
import pytest

@pytest.fixture
def email_service(monkeypatch):
    # Provide a minimal config module using types.ModuleType so services.email_service imports cleanly
    config = types.ModuleType("config")
    config.EMAIL_HOST = "smtp.test.com"
    config.EMAIL_PORT = 587
    config.EMAIL_USER = "user"
    config.EMAIL_PASSWORD = "password"
    config.EMAIL_FROM_ADDRESS = "from@test.com"
    config.EMAIL_FROM_NAME = "Test"
    config.SITE_URL = "https://example.com"
    
    monkeypatch.setitem(sys.modules, "config", config)
    sys.modules.pop("services.email_service", None)
    return importlib.import_module("services.email_service")

def test_digest_email_links_point_to_recommendations(email_service):
    assert email_service.DASHBOARD_URL.endswith("/recommendations/")
    
    html = email_service.build_digest_html(
        profile_name="Test Profile",
        papers=[
            {
                "arxiv_id": "2301.00001",
                "title": "Test Paper",
                "score": 0.95,
                # 4 sentences to trigger summary truncation and verify the "Read more" link
                "summary_text": "One. Two. Three. Four.",
            }
        ],
        run_date="2026-09-04",
        shown=1,
        total=1,
        frequency="daily",
    )
    
    # Verify DASHBOARD_URL is used in header logo, conditional "Read more" link, and main CTA
    assert html.count(email_service.DASHBOARD_URL) >= 3