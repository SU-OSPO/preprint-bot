"""Tests for the env-overridable USER_AGENT setting."""
import importlib

import preprint_sources.settings as settings


def test_default_user_agent(monkeypatch):
    monkeypatch.delenv("PREPRINT_SOURCES_USER_AGENT", raising=False)
    importlib.reload(settings)
    assert settings.USER_AGENT == "PreprintBot/1.0"


def test_env_override(monkeypatch):
    monkeypatch.setenv("PREPRINT_SOURCES_USER_AGENT", "Custom/9.9")
    importlib.reload(settings)
    assert settings.USER_AGENT == "Custom/9.9"
    # Restore the module to its default state for other tests.
    monkeypatch.delenv("PREPRINT_SOURCES_USER_AGENT", raising=False)
    importlib.reload(settings)
