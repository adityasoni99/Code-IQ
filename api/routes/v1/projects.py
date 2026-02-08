"""Project routes for edit: create from job, PATCH, regenerate."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api import job_store, project_store
from api.runner import run_job

logger = logging.getLogger("codebase_knowledge_builder.api")

router = APIRouter()


class ProjectCreateFromJobResponse(BaseModel):
    project_id: str
    summary: str
    chapters: list[dict[str, Any]]


class ProjectUpdateBody(BaseModel):
    summary: str | None = None
    chapters: list[dict[str, Any]] | None = None


class RegenerateBody(BaseModel):
    scope: str = Field(default="full", description="full or chapter (chapter not implemented)")


class RegenerateResponse(BaseModel):
    job_id: str
    message: str = "Poll GET /v1/jobs/{job_id} for status."


@router.post("/projects/from-job/{job_id}", status_code=201)
def create_project_from_job(job_id: str) -> dict[str, Any]:
    """Create a project from a completed job's result. 404 if job not found or not completed."""
    rec = job_store.get_job_internal(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    if rec.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed.")
    result = rec.get("result") or {}
    summary = result.get("summary") or ""
    chapters = result.get("chapters") or []
    inputs = rec.get("inputs") or {}
    source_inputs = {k: v for k, v in inputs.items() if k != "_temp_dir"}
    project_id = project_store.create_project(summary, chapters, source_inputs)
    return {
        "project_id": project_id,
        "summary": summary,
        "chapters": chapters,
    }


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    """Get project (summary, chapters). 404 if not found."""
    rec = project_store.get_project(project_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Project not found.")
    return rec


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: ProjectUpdateBody) -> dict[str, Any]:
    """Update summary and/or chapters. 404 if not found."""
    ok = project_store.update_project(project_id, summary=body.summary, chapters=body.chapters)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found.")
    rec = project_store.get_project(project_id)
    return rec


@router.post("/projects/{project_id}/regenerate", status_code=202)
def regenerate_project(project_id: str, body: RegenerateBody) -> RegenerateResponse:
    """Enqueue a new job with project's source inputs (full only). Returns job_id."""
    if body.scope != "full":
        raise HTTPException(status_code=400, detail="Only scope=full is supported.")
    rec = project_store.get_project_internal(project_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Project not found.")
    source_inputs = rec.get("source_inputs") or {}
    if not source_inputs.get("repo_url") and not source_inputs.get("local_dir"):
        raise HTTPException(status_code=400, detail="Project has no source inputs for regenerate.")
    job_id = job_store.create_job(source_inputs, webhook_url=None)
    import threading
    t = threading.Thread(target=run_job, args=(job_id,))
    t.daemon = True
    t.start()
    return RegenerateResponse(job_id=job_id)
