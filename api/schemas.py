"""Pydantic request/response models for the API."""

from pydantic import BaseModel, Field


class BuildRequest(BaseModel):
    """Request body for POST /v1/build and POST /v1/jobs."""

    repo_url: str | None = Field(default=None, description="GitHub repository URL")
    project_name: str | None = Field(default=None, description="Project name for output")
    language: str = Field(default="english", description="Tutorial language")
    output_dir: str = Field(default="output", description="Base directory for output")
    github_token: str | None = Field(default=None, description="GitHub API token (optional)")


class BuildResponse(BaseModel):
    """Response body for successful POST /v1/build."""

    final_output_dir: str = Field(..., description="Path to generated tutorial directory")
    summary: str | None = Field(default=None, description="Project summary from pipeline")


class BuildTimeoutResponse(BaseModel):
    """Response body when sync build exceeds max duration (202)."""

    job_id: str = Field(..., description="Async job ID; poll GET /v1/jobs/{id}")
    message: str = Field(
        default="Run exceeded max duration; poll GET /v1/jobs/{id} for status.",
        description="Human-readable message",
    )


class JobCreateRequest(BuildRequest):
    """Request body for POST /v1/jobs (same as build + optional webhook_url)."""

    webhook_url: str | None = Field(default=None, description="Callback URL on completion/failure (optional)")


class RecursiveJobRequest(BaseModel):
    """Request body for POST /v1/jobs/recursive."""

    parent_dirs: list[str] = Field(..., description="Parent directory paths to recurse into")
    file_threshold: int = Field(default=100, description="Recursion file count threshold")
    parallel: int = Field(default=0, description="Parallel workers (0 = sequential)")
    resume: bool = Field(default=True, description="Skip already-completed folders")
    output_dir: str = Field(default="output", description="Base directory for output")
    language: str = Field(default="english", description="Tutorial language")
    github_token: str | None = Field(default=None, description="GitHub API token (optional)")


class JobResponse(BaseModel):
    """Response for GET /v1/jobs/{job_id}."""

    job_id: str
    status: str  # queued | running | completed | failed
    created_at: float
    updated_at: float
    result: dict | None = None
    error: str | None = None
    progress: dict | None = None  # {"completed": int, "total": int, "current_folder": str}
    mode: str = "single"  # "single" | "recursive"


class JobCreateResponse(BaseModel):
    """Response for POST /v1/jobs (201)."""

    job_id: str
    status: str = "queued"
