"""Tests for webhook delivery: payload, signature, retries."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from api import job_store
from api.webhooks import _sign_payload, deliver_webhook


def test_sign_payload_empty_secret():
    """With empty secret, signature is empty string."""
    assert _sign_payload(b'{"a":1}', "") == ""


def test_sign_payload_with_secret():
    """With secret, signature is HMAC-SHA256 hex."""
    sig = _sign_payload(b'{"job_id":"x","status":"completed"}', "my-secret")
    assert isinstance(sig, str)
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_deliver_webhook_post_called_with_payload_and_signature():
    """deliver_webhook POSTs to webhook_url with JSON payload and X-Webhook-Signature."""
    with patch("api.webhooks.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        with patch("api.webhooks.WEBHOOK_SECRET", "test-secret"):
            deliver_webhook(
                "https://example.com/callback",
                job_id="j1",
                status="completed",
                result={"final_output_dir": "/out"},
                completed_at=1234567890.0,
            )
    assert mock_post.call_count == 1
    call_args, call_kw = mock_post.call_args
    assert call_args[0] == "https://example.com/callback"
    body = json.loads(call_kw["data"].decode("utf-8"))
    assert body["job_id"] == "j1"
    assert body["status"] == "completed"
    assert body["result"]["final_output_dir"] == "/out"
    assert body["completed_at"] == 1234567890.0
    headers = call_kw["headers"]
    assert "X-Webhook-Signature" in headers
    expected_sig = _sign_payload(call_kw["data"], "test-secret")
    assert headers["X-Webhook-Signature"] == expected_sig
    assert headers.get("Delivery-Attempt") == "1"


def test_deliver_webhook_retries_on_500():
    """On 500 response, retries up to MAX_ATTEMPTS."""
    with patch("api.webhooks.requests.post") as mock_post:
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Server Error"
        with patch("api.webhooks.time.sleep"):
            deliver_webhook(
                "https://example.com/cb",
                job_id="j2",
                status="failed",
                error="Pipeline failed",
            )
    assert mock_post.call_count == 3


def test_deliver_webhook_skips_empty_url():
    """Empty webhook_url does not POST."""
    with patch("api.webhooks.requests.post") as mock_post:
        deliver_webhook("", job_id="j3", status="completed")
        deliver_webhook("   ", job_id="j3", status="completed")
    assert mock_post.call_count == 0
