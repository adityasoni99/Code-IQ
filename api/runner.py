"""Background runner: run pipeline for a job and update job store."""

import logging
import os
import shutil
import time
from typing import Any

from api import job_store
from api.schemas import BuildRequest

logger = logging.getLogger("codebase_knowledge_builder.api.runner")


def _inputs_to_shared(inputs: dict[str, Any]) -> dict[str, Any]:
    """Build shared store from job inputs (same as build route)."""
    from shared_schema import default_shared_store

    shared = default_shared_store()
    shared["repo_url"] = (inputs.get("repo_url") or "").strip() or None
    shared["local_dir"] = (inputs.get("local_dir") or "").strip() or None
    shared["project_name"] = (inputs.get("project_name") or "").strip() or None
    shared["output_dir"] = (inputs.get("output_dir") or "output").strip()
    shared["language"] = (inputs.get("language") or "english").strip()
    shared["github_token"] = inputs.get("github_token") or os.environ.get("GITHUB_TOKEN")
    return shared


def _run_flow(shared: dict[str, Any]) -> None:
    from flow import create_full_flow

    flow = create_full_flow()
    flow.run(shared)


def run_job(job_id: str) -> None:
    """
    Run the pipeline for the given job.
    Updates job store: running -> completed (with result) or failed (with error).
    Webhook delivery is done in task 4.0.
    """
    rec = job_store.get_job_internal(job_id)
    if not rec:
        logger.warning("Job %s not found or expired", job_id)
        return
    if rec["status"] not in ("queued", "running"):
        return
    inputs = rec.get("inputs") or {}
    job_store.update_status(job_id, "running")
    temp_dir = inputs.get("_temp_dir")  # cleanup after run (upload jobs)
    try:
        shared = _inputs_to_shared(inputs)
        _run_flow(shared)
        final_dir = shared.get("final_output_dir")
        summary = None
        rel = shared.get("relationships") or {}
        if isinstance(rel, dict):
            summary = rel.get("summary")
        # Chapters for edit/API: list of { name, content }
        chapters = []
        abstractions = shared.get("abstractions") or []
        chapter_order = shared.get("chapter_order") or []
        shared_chapters = shared.get("chapters") or []
        for idx in chapter_order:
            if idx < len(abstractions) and idx < len(shared_chapters):
                name = abstractions[idx].get("name", f"Chapter {idx + 1}") if isinstance(abstractions[idx], dict) else f"Chapter {idx + 1}"
                chapters.append({"name": name, "content": shared_chapters[idx]})
        result = {"final_output_dir": final_dir, "summary": summary, "chapters": chapters}
        job_store.update_status(job_id, "completed", result=result)
        logger.info("Job %s completed: %s", job_id, final_dir)
        webhook_url = rec.get("webhook_url")
        if webhook_url:
            from api.webhooks import deliver_webhook
            deliver_webhook(webhook_url, job_id, "completed", result=result, completed_at=time.time())
    except Exception as e:
        logger.exception("Job %s failed: %s", job_id, e)
        job_store.update_status(job_id, "failed", error=str(e))
        webhook_url = rec.get("webhook_url")
        if webhook_url:
            from api.webhooks import deliver_webhook
            deliver_webhook(webhook_url, job_id, "failed", error=str(e), completed_at=time.time())
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info("Removed temp dir %s", temp_dir)
            except OSError as e:
                logger.warning("Failed to remove temp dir %s: %s", temp_dir, e)
