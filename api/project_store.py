"""In-memory project store for edit (Phase 2)."""

import time
import uuid
from typing import Any

_store: dict[str, dict[str, Any]] = {}


def create_project(summary: str, chapters: list[dict[str, Any]], source_inputs: dict[str, Any] | None = None) -> str:
    """Create project from summary, chapters, and optional source_inputs for regenerate."""
    project_id = str(uuid.uuid4())
    now = time.time()
    _store[project_id] = {
        "project_id": project_id,
        "summary": summary,
        "chapters": chapters,
        "source_inputs": source_inputs or {},
        "created_at": now,
        "updated_at": now,
    }
    return project_id


def get_project(project_id: str) -> dict[str, Any] | None:
    """Return project record (no source_inputs in response for GET)."""
    if project_id not in _store:
        return None
    rec = _store[project_id].copy()
    rec.pop("source_inputs", None)
    return rec


def get_project_internal(project_id: str) -> dict[str, Any] | None:
    """Return full project including source_inputs (for regenerate)."""
    return _store.get(project_id)


def update_project(project_id: str, summary: str | None = None, chapters: list[dict[str, Any]] | None = None) -> bool:
    """Update summary and/or chapters. Returns True if found."""
    if project_id not in _store:
        return False
    now = time.time()
    if summary is not None:
        _store[project_id]["summary"] = summary
    if chapters is not None:
        _store[project_id]["chapters"] = chapters
    _store[project_id]["updated_at"] = now
    return True
