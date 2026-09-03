import pytest
from preprint_bot.pipeline import _format_duration

def test_format_duration_seconds():
    assert _format_duration(45.5) == "45.50s"
    assert _format_duration(5.123) == "5.12s"

def test_format_duration_minutes():
    assert _format_duration(90) == "1m 30.0s"
    assert _format_duration(125.4) == "2m 5.4s"

def test_format_duration_hours():
    assert _format_duration(3661) == "1h 1m 1.0s"
    assert _format_duration(7325.5) == "2h 2m 5.5s"