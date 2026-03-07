"""Tests for startup and settings safety guards."""

from __future__ import annotations

import pytest

import marketpulse.main as app_main
from marketpulse.core.config import Settings


def test_settings_debug_release_string_maps_to_false(monkeypatch):
    monkeypatch.setenv("DEBUG", "release")
    settings = Settings()
    assert settings.debug is False


def test_startup_security_requires_api_key_in_production(monkeypatch):
    monkeypatch.setattr(app_main.settings, "environment", "production")
    monkeypatch.setattr(app_main.settings, "api_key", "")
    with pytest.raises(RuntimeError, match="API_KEY"):
        app_main.ensure_startup_security()


def test_startup_security_allows_development_without_api_key(monkeypatch):
    monkeypatch.setattr(app_main.settings, "environment", "development")
    monkeypatch.setattr(app_main.settings, "api_key", "")
    app_main.ensure_startup_security()

