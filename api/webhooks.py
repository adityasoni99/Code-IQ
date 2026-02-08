"""Webhook delivery: signed POST on job completion/failure with retries."""

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger("codebase_knowledge_builder.api.webhooks")

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
MAX_ATTEMPTS = 3
BACKOFF_BASE = 1  # seconds


def _sign_payload(body: bytes, secret: str) -> str:
    """HMAC-SHA256 of body with secret; return hex digest."""
    if not secret:
        return ""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def deliver_webhook(
    webhook_url: str,
    job_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    completed_at: float | None = None,
) -> None:
    """
    POST to webhook_url with JSON payload and X-Webhook-Signature (HMAC-SHA256 of body).
    Retries up to MAX_ATTEMPTS with exponential backoff on non-2xx or timeout.
    Sets Delivery-Attempt: 1..3 header.
    """
    if not webhook_url or not webhook_url.strip():
        return
    completed_at = completed_at or time.time()
    payload = {
        "job_id": job_id,
        "status": status,
        "result": result,
        "error": error,
        "completed_at": completed_at,
    }
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = _sign_payload(body, WEBHOOK_SECRET)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
    }
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        headers["Delivery-Attempt"] = str(attempt)
        try:
            r = requests.post(webhook_url, data=body, headers=headers, timeout=30)
            if 200 <= r.status_code < 300:
                logger.info("Webhook delivered to %s for job %s (attempt %d)", webhook_url, job_id, attempt)
                return
            last_exc = RuntimeError(f"Webhook returned {r.status_code}: {r.text[:200]}")
        except requests.RequestException as e:
            last_exc = e
        logger.warning("Webhook attempt %d failed for job %s: %s", attempt, job_id, last_exc)
        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
    logger.error("Webhook delivery failed after %d attempts for job %s: %s", MAX_ATTEMPTS, job_id, last_exc)
