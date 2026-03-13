"""Tests for safe model-loading behavior from S3."""

from __future__ import annotations

import io
import json
import joblib
from types import SimpleNamespace

import marketpulse.infrastructure.s3 as s3_utils


def _joblib_dumps(obj):
    """Serialize an object using joblib and return bytes."""
    buf = io.BytesIO()
    joblib.dump(obj, buf, compress=("zlib", 3))
    return buf.getvalue()


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
        "allow_unsafe_model_pickle": False,
        "s3_model_bucket": "model-bucket",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_load_model_skips_insecure_pickle_in_production(monkeypatch):
    monkeypatch.setattr(
        s3_utils,
        "get_settings",
        lambda: _settings(environment="production", model_signing_key="", allow_unsafe_model_pickle=False),
    )
    monkeypatch.setattr(s3_utils, "_s3_client", lambda: (_ for _ in ()).throw(AssertionError("should not hit s3")))
    assert s3_utils.load_model("Snacks") is None


def test_load_model_returns_none_on_signature_mismatch(monkeypatch):
    payload_obj = {"model": "demo"}
    payload = _joblib_dumps(payload_obj)
    bad_signature = json.dumps({"algo": "hmac-sha256", "digest": "deadbeef"}).encode("utf-8")
    objects = {
        "snacks/latest.pkl": payload,
        "snacks/latest.pkl.sig.json": bad_signature,
    }
    monkeypatch.setattr(s3_utils, "get_settings", lambda: _settings(model_signing_key="secret-key"))
    monkeypatch.setattr(s3_utils, "_s3_client", lambda: _FakeS3Client(objects))
    assert s3_utils.load_model("Snacks") is None


def test_load_model_returns_object_when_signature_valid(monkeypatch):
    payload_obj = {"model": "demo"}
    payload = _joblib_dumps(payload_obj)
    algo, digest = s3_utils._signature_for_payload(payload, "secret-key")
    signature = json.dumps({"algo": algo, "digest": digest}).encode("utf-8")
    objects = {
        "snacks/latest.pkl": payload,
        "snacks/latest.pkl.sig.json": signature,
    }
    monkeypatch.setattr(s3_utils, "get_settings", lambda: _settings(model_signing_key="secret-key"))
    monkeypatch.setattr(s3_utils, "_s3_client", lambda: _FakeS3Client(objects))
    assert s3_utils.load_model("Snacks") == payload_obj

