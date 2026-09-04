import sys
from unittest.mock import MagicMock

# Mock config module to satisfy email_service imports during pytest collection
mock_config = MagicMock()
mock_config.EMAIL_HOST = "smtp.test.com"
mock_config.EMAIL_PORT = 587
mock_config.EMAIL_USER = "user"
mock_config.EMAIL_PASSWORD = "password"
mock_config.EMAIL_FROM_ADDRESS = "from@test.com"
mock_config.EMAIL_FROM_NAME = "Test"
mock_config.SITE_URL = "https://example.com"
sys.modules["config"] = mock_config

from services.email_service import build_digest_html, DASHBOARD_URL

def test_digest_email_links_point_to_recommendations():
    assert DASHBOARD_URL.endswith("/recommendations/")
    
    html = build_digest_html(
        profile_name="Test Profile",
        papers=[{"arxiv_id": "2301.00001", "title": "Test Paper", "score": 0.95}],
        run_date="2026-09-04",
        shown=1,
        total=1,
        frequency="daily"
    )
    
    assert "/recommendations/" in html