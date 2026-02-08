"""Sync build endpoint: POST /v1/build."""

import logging
import os
import threading
from typing import Any

from fastapi import APIRouter, HTTPException

from api.schemas import BuildRequest, BuildResponse

logger = logging.getLogger("codebase_knowledge_builder.api")

router = APIRouter()

# Max duration for sync build (seconds). If exceeded, return 413.
# 202 + job_id will be available when async API (task 2.0) is implemented.
BUILD_TIMEOUT_SECONDS = int(os.environ.get("BUILD_TIMEOUT_SECONDS", "300"))  # 5 min


def _request_to_shared(body: BuildRequest) -> dict[str, Any]:
    """Build shared store from request body and defaults."""
    from shared_schema import default_shared_store

    shared = default_shared_store()
    shared["repo_url"] = body.repo_url.strip() if body.repo_url else None
    shared["local_dir"] = None  # Upload supported later (task 5.0)
    shared["project_name"] = body.project_name.strip() if body.project_name else None
    shared["output_dir"] = (body.output_dir or "output").strip()
    shared["language"] = (body.language or "english").strip()
    shared["github_token"] = body.github_token or os.environ.get("GITHUB_TOKEN")
    return shared


def _run_flow_sync(shared: dict[str, Any]) -> None:
    """Run the full flow in the current thread. Mutates shared."""
    from flow import create_full_flow

    flow = create_full_flow()
    flow.run(shared)


@router.post("/build", response_model=BuildResponse)
def post_build(body: BuildRequest) -> BuildResponse:
    """
    Run the tutorial pipeline synchronously.

    Requires exactly one of: repo_url (Phase 1). Upload support in a later phase.
    On success returns final_output_dir and summary.
    If the run exceeds BUILD_TIMEOUT_SECONDS (default 300), returns 413.
    """
    # Validate: require repo_url for Phase 1 (no upload yet)
    if not body.repo_url or not body.repo_url.strip():
        raise HTTPException(
            status_code=400,
            detail="Provide repo_url. Upload will be supported in a later release.",
        )

    shared = _request_to_shared(body)
    result: dict[str, Any] = {}
    exc_holder: list[BaseException] = []

    def run() -> None:
        try:
            _run_flow_sync(shared)
            result["shared"] = shared
        except BaseException as e:
            exc_holder.append(e)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=BUILD_TIMEOUT_SECONDS)

    if exc_holder:
        raise HTTPException(status_code=500, detail=str(exc_holder[0]))

    if thread.is_alive():
        # Timeout: run exceeded max duration
        raise HTTPException(
            status_code=413,
            detail=f"Run exceeded max duration ({BUILD_TIMEOUT_SECONDS}s). Use async POST /v1/jobs when available.",
        )

    if "shared" not in result:
        raise HTTPException(status_code=500, detail="Pipeline did not produce output.")

    out_shared = result["shared"]
    final_dir = out_shared.get("final_output_dir")
    if not final_dir:
        raise HTTPException(status_code=500, detail="Pipeline did not set final_output_dir.")

    summary = None
    rel = out_shared.get("relationships") or {}
    if isinstance(rel, dict):
        summary = rel.get("summary")

    return BuildResponse(final_output_dir=final_dir, summary=summary)
