"""Tests for safe model-loading behavior from S3 (JSON-based serialization)."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import marketpulse.infrastructure.s3 as s3_utils


class _FakeS3Client:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self._objects = objects

    def get_object(self, Bucket: str, Key: str):  # noqa: N803 - boto3 style
        if Key not in self._objects:
            raise s3_utils.ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self._objects[Key])}


def _settings(**overrides):
    base = {
        "environment": "development",
        "model_signing_key": "",
        "s3_model_bucket": "model-bucket",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _sample_model_json() -> dict:
    """Return a minimal valid JSON model payload."""
    return {
        "schema_version": "1.0",
        "trained_at": "20260315T000000Z",
        "feature_columns": ["time_index", "weekday"],
        "model": {
            "coef_": [0.5, -0.2],
            "intercept_": 10.0,
            "alpha_": 1e-6,
            "lambda_": 1e-6,
            "sigma_": [[1.0, 0.0], [0.0, 1.0]],
        },
        "scaler": {
            "scale_": [1.0, 1.0],
            "mean_": [0.0, 0.0],
            "var_": [1.0, 1.0],
            "n_samples_seen_": 100,
        },
    }


def test_load_model_returns_none_when_key_missing(monkeypatch):
    """load_model returns None when the model key doesn't exist in S3."""
    monkeypatch.setattr(s3_utils, "get_settings", lambda: _settings())
    monkeypatch.setattr(s3_utils, "_s3_client", lambda: _FakeS3Client({}))
    assert s3_utils.load_model("Snacks") is None


def test_load_model_returns_none_on_signature_mismatch(monkeypatch):
    """load_model returns None when signing key is set but signature doesn't match."""
    payload_dict = _sample_model_json()
    payload = json.dumps(payload_dict).encode("utf-8")
    bad_signature = json.dumps({"algo": "hmac-sha256", "digest": "deadbeef"}).encode("utf-8")
    objects = {
        "snacks/latest.json": payload,
        "snacks/latest.json.sig.json": bad_signature,
    }
    monkeypatch.setattr(s3_utils, "get_settings", lambda: _settings(model_signing_key="secret-key"))
    monkeypatch.setattr(s3_utils, "_s3_client", lambda: _FakeS3Client(objects))
    assert s3_utils.load_model("Snacks") is None


def test_load_model_returns_object_when_signature_valid(monkeypatch):
    """load_model returns the deserialized JSON dict when signature is valid."""
    payload_dict = _sample_model_json()
    payload = json.dumps(payload_dict).encode("utf-8")
    algo, digest = s3_utils._signature_for_payload(payload, "secret-key")
    signature = json.dumps({"algo": algo, "digest": digest}).encode("utf-8")
    objects = {
        "snacks/latest.json": payload,
        "snacks/latest.json.sig.json": signature,
    }
    monkeypatch.setattr(s3_utils, "get_settings", lambda: _settings(model_signing_key="secret-key"))
    monkeypatch.setattr(s3_utils, "_s3_client", lambda: _FakeS3Client(objects))
    result = s3_utils.load_model("Snacks")
    assert result == payload_dict


def test_load_model_returns_object_without_signing_key(monkeypatch):
    """load_model returns the JSON dict when no signing key is configured (dev mode)."""
    payload_dict = _sample_model_json()
    payload = json.dumps(payload_dict).encode("utf-8")
    objects = {
        "snacks/latest.json": payload,
    }
    monkeypatch.setattr(s3_utils, "get_settings", lambda: _settings(model_signing_key=""))
    monkeypatch.setattr(s3_utils, "_s3_client", lambda: _FakeS3Client(objects))
    result = s3_utils.load_model("Snacks")
    assert result == payload_dict
