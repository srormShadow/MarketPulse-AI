"""Tests for backward-compatible settings environment aliases."""

from __future__ import annotations

from marketpulse.core.config import Settings


def test_settings_accepts_s3_models_bucket_env_alias(monkeypatch):
    monkeypatch.setenv("S3_MODELS_BUCKET", "marketpulse-model-artifacts")
    settings = Settings()
    assert settings.s3_model_bucket == "marketpulse-model-artifacts"


def test_settings_prefers_primary_s3_model_bucket_env(monkeypatch):
    monkeypatch.setenv("S3_MODEL_BUCKET", "primary-model-bucket")
    monkeypatch.setenv("S3_MODELS_BUCKET", "legacy-model-bucket")
    settings = Settings()
    assert settings.s3_model_bucket == "primary-model-bucket"

