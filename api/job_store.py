"""In-memory job store for async build jobs."""

import time
import uuid
from typing import Any

# In-memory store: job_id -> job record.
# Optional: cleanup jobs older than JOB_RETENTION_SECONDS (e.g. 24 h).
_store: dict[str, dict[str, Any]] = {}
JOB_RETENTION_SECONDS = int(__import__("os").environ.get("JOB_RETENTION_SECONDS", "86400"))  # 24 h


def create_job(inputs: dict[str, Any], webhook_url: str | None = None) -> str:
    """Create a new job with status queued. Returns job_id."""
    job_id = str(uuid.uuid4())
    now = time.time()
    _store[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "inputs": inputs,
        "webhook_url": webhook_url,  # not exposed in get_job response
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    return job_id


def update_status(
    job_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Update job status and optionally result or error."""
    if job_id not in _store:
        return
    now = time.time()
    _store[job_id]["status"] = status
    _store[job_id]["updated_at"] = now
    if result is not None:
        _store[job_id]["result"] = result
    if error is not None:
        _store[job_id]["error"] = error


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return job record for API response (no webhook_url, no inputs). None if missing or expired."""
    _cleanup_expired()
    if job_id not in _store:
        return None
    rec = _store[job_id]
    age = time.time() - rec["created_at"]
    if age > JOB_RETENTION_SECONDS:
        del _store[job_id]
        return None
    return {
        "job_id": rec["job_id"],
        "status": rec["status"],
        "created_at": rec["created_at"],
        "updated_at": rec["updated_at"],
        "result": rec.get("result"),
        "error": rec.get("error"),
    }


def get_job_internal(job_id: str) -> dict[str, Any] | None:
    """Return full job record including inputs and webhook_url (for runner)."""
    _cleanup_expired()
    return _store.get(job_id)


def _cleanup_expired() -> None:
    """Remove jobs older than JOB_RETENTION_SECONDS."""
    now = time.time()
    to_remove = [jid for jid, rec in _store.items() if now - rec["created_at"] > JOB_RETENTION_SECONDS]
    for jid in to_remove:
        del _store[jid]
