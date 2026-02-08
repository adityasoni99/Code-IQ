"""Async job routes: POST /v1/jobs, POST /v1/jobs/upload, GET /v1/jobs/{id}, GET /v1/jobs/{id}/result."""

import io
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from api import job_store
from api.runner import run_job
from api.schemas import JobCreateRequest, JobCreateResponse, JobResponse

logger = logging.getLogger("codebase_knowledge_builder.api")

router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _body_to_inputs(body: JobCreateRequest) -> dict:
    """Convert request body to job inputs dict (stored in job)."""
    return {
        "repo_url": body.repo_url,
        "project_name": body.project_name,
        "language": body.language,
        "output_dir": body.output_dir,
        "github_token": body.github_token,
        "local_dir": getattr(body, "local_dir", None),
    }


@router.post("/jobs", response_model=JobCreateResponse, status_code=201)
def post_jobs(body: JobCreateRequest) -> JSONResponse:
    """
    Create an async job. Same inputs as POST /v1/build.
    Returns job_id; poll GET /v1/jobs/{id} for status.
    """
    if not body.repo_url or not body.repo_url.strip():
        raise HTTPException(
            status_code=400,
            detail="Provide repo_url. Upload will be supported in a later release.",
        )
    inputs = _body_to_inputs(body)
    webhook_url = body.webhook_url.strip() if body.webhook_url else None
    job_id = job_store.create_job(inputs, webhook_url=webhook_url)
    # Run in background thread
    import threading
    t = threading.Thread(target=run_job, args=(job_id,))
    t.daemon = True
    t.start()
    return JSONResponse(
        content={"job_id": job_id, "status": "queued"},
        status_code=201,
        headers={"Location": f"/v1/jobs/{job_id}"},
    )


@router.post("/jobs/upload", status_code=201)
def post_jobs_upload(
    file: UploadFile = File(..., description="Zip file of project"),
    project_name: str | None = Form(None),
    language: str = Form("english"),
    webhook_url: str | None = Form(None),
) -> JSONResponse:
    """
    Create an async job from an uploaded zip. Extracts to temp dir, runs pipeline with local_dir.
    Max size 50 MB. Temp dir is removed after run (success or failure).
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a .zip file.")
    # Read and check size (stream in chunks to avoid loading full file if huge)
    size = 0
    chunks = []
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"Max upload size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.")
        chunks.append(chunk)
    zip_bytes = b"".join(chunks)
    try:
        temp_dir = tempfile.mkdtemp(prefix="ckb_upload_")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to create temp dir: {e}")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            zf.extractall(temp_dir)
    except zipfile.BadZipFile as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Invalid zip: {e}")
    inputs = {
        "repo_url": None,
        "local_dir": temp_dir,
        "project_name": (project_name or "").strip() or None,
        "language": (language or "english").strip(),
        "output_dir": "output",
        "github_token": None,
        "_temp_dir": temp_dir,  # runner will delete after run
    }
    webhook_url = (webhook_url or "").strip() or None
    job_id = job_store.create_job(inputs, webhook_url=webhook_url)
    import threading
    t = threading.Thread(target=run_job, args=(job_id,))
    t.daemon = True
    t.start()
    return JSONResponse(
        content={"job_id": job_id, "status": "queued"},
        status_code=201,
        headers={"Location": f"/v1/jobs/{job_id}"},
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    """Get job status. 404 if unknown or expired."""
    rec = job_store.get_job(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return JobResponse(**rec)


def _zip_directory(path: str) -> io.BytesIO:
    """Create a zip of the directory in memory."""
    buf = io.BytesIO()
    p = Path(path)
    if not p.is_dir():
        raise ValueError(f"Not a directory: {path}")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in p.rglob("*"):
            if f.is_file():
                arcname = f.relative_to(p)
                zf.write(f, arcname)
    buf.seek(0)
    return buf


@router.get("/jobs/{job_id}/result")
def get_job_result(job_id: str) -> StreamingResponse:
    """
    Return zip of output directory when status is completed.
    409 when queued/running; 404 when failed or missing.
    """
    rec = job_store.get_job(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    if rec["status"] in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Job not yet completed. Poll GET /v1/jobs/{id}.")
    if rec["status"] == "failed":
        raise HTTPException(status_code=404, detail="Job failed. Check GET /v1/jobs/{id} for error.")
    result = rec.get("result") or {}
    final_dir = result.get("final_output_dir")
    if not final_dir or not Path(final_dir).is_dir():
        raise HTTPException(status_code=404, detail="Result directory not available.")
    buf = _zip_directory(final_dir)
    # Name zip after project (last part of path)
    name = Path(final_dir).name or "tutorial"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}.zip"'},
    )
