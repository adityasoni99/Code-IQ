"""In-memory job store for async build jobs. Persisted to JSON so jobs survive server reloads."""

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

# In-memory store: job_id -> job record.
# Optional: cleanup jobs older than JOB_RETENTION_SECONDS (e.g. 24 h).
_store: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()
JOB_RETENTION_SECONDS = int(os.environ.get("JOB_RETENTION_SECONDS", "86400"))  # 24 h

# Persistence: .cache/jobs.json under project root (excluded from uvicorn reload)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_JOBS_FILE = _PROJECT_ROOT / ".cache" / "jobs.json"


def _persist() -> None:
    """Write store to JSON. Caller should hold _lock if needed."""
    try:
        _JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_JOBS_FILE, "w") as f:
            json.dump(_store, f)
    except OSError:
        pass  # Non-fatal; in-memory store still works


def _load() -> None:
    """Load store from JSON at module init."""
    if not _JOBS_FILE.is_file():
        return
    try:
        with open(_JOBS_FILE) as f:
            loaded = json.load(f)
        with _lock:
            _store.clear()
            _store.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass


def create_job(inputs: dict[str, Any], webhook_url: str | None = None) -> str:
    """Create a new job with status queued. Returns job_id."""
    job_id = str(uuid.uuid4())
    now = time.time()
    with _lock:
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
        _persist()
    return job_id


def update_status(
    job_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Update job status and optionally result or error."""
    with _lock:
        if job_id not in _store:
            return
        now = time.time()
        _store[job_id]["status"] = status
        _store[job_id]["updated_at"] = now
        if result is not None:
            _store[job_id]["result"] = result
        if error is not None:
            _store[job_id]["error"] = error
        _persist()


def update_progress(
    job_id: str,
    *,
    step: int | None = None,
    total_steps: int | None = None,
    step_current: int | None = None,
    step_total: int | None = None,
    step_name: str = "",
    detail: str = "",
    completed: int | None = None,
    total: int | None = None,
    current_folder: str = "",
) -> None:
    """Update job progress. Use step/total_steps/step_name/detail for single jobs; completed/total/current_folder for recursive.
    step_current/step_total optional: sub-progress within current step (e.g. chapter 3 of 6 within step 6)."""
    with _lock:
        if job_id not in _store:
            return
        _store[job_id]["updated_at"] = time.time()
        progress = _store[job_id].get("progress") or {}
        if step is not None:
            progress["step"] = step
        if total_steps is not None:
            progress["total_steps"] = total_steps
        if step_current is not None:
            progress["step_current"] = step_current
        if step_total is not None:
            progress["step_total"] = step_total
        if step_name:
            progress["step_name"] = step_name
        if detail:
            progress["detail"] = detail
        if completed is not None:
            progress["completed"] = completed
        if total is not None:
            progress["total"] = total
        if current_folder:
            progress["current_folder"] = current_folder
        _store[job_id]["progress"] = progress
        _persist()


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return job record for API response (no webhook_url, no inputs). None if missing or expired."""
    with _lock:
        _cleanup_expired()
        if job_id not in _store:
            return None
        rec = _store[job_id]
        age = time.time() - rec["created_at"]
        if age > JOB_RETENTION_SECONDS:
            del _store[job_id]
            _persist()
            return None
        return {
            "job_id": rec["job_id"],
            "status": rec["status"],
            "created_at": rec["created_at"],
            "updated_at": rec["updated_at"],
            "result": rec.get("result"),
            "error": rec.get("error"),
            "progress": rec.get("progress"),
            "mode": rec.get("inputs", {}).get("mode", "single"),
        }


def get_job_internal(job_id: str) -> dict[str, Any] | None:
    """Return full job record including inputs and webhook_url (for runner)."""
    with _lock:
        _cleanup_expired()
        return _store.get(job_id)


def _cleanup_expired() -> None:
    """Remove jobs older than JOB_RETENTION_SECONDS. Caller must hold _lock."""
    now = time.time()
    to_remove = [jid for jid, rec in _store.items() if now - rec["created_at"] > JOB_RETENTION_SECONDS]
    for jid in to_remove:
        del _store[jid]
    if to_remove:
        _persist()


# Load persisted jobs on startup (survives uvicorn reload)
_load()
