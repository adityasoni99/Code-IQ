"""Tutorial browser routes: list and serve tutorials from the configurable output directory."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/tutorials", tags=["tutorials"])

_OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "out")).resolve()

_CONTENT_TYPES = {
    ".md": "text/markdown",
    ".html": "text/html",
    ".json": "application/json",
    ".txt": "text/plain",
    ".css": "text/css",
    ".js": "application/javascript",
}


def _safe_relative_path(base: Path, requested: str) -> Path:
    """Resolve path ensuring no traversal outside base. Raises HTTPException if invalid."""
    requested = (requested or "").strip().lstrip("/")
    if not requested:
        raise HTTPException(status_code=400, detail="File path is required.")
    parts = requested.replace("\\", "/").split("/")
    if ".." in parts:
        raise HTTPException(status_code=400, detail="Path traversal not allowed.")
    resolved = (base / requested).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path traversal not allowed.")
    return resolved


@router.get("")
def list_tutorials():
    """
    List tutorial folders in the output directory. Returns subfolders that contain index.md.
    """
    if not _OUTPUT_DIR.is_dir():
        return []
    result = []
    for entry in sorted(_OUTPUT_DIR.iterdir()):
        if not entry.is_dir():
            continue
        index_md = entry / "index.md"
        result.append({
            "name": entry.name,
            "slug": entry.name,
            "hasIndex": index_md.is_file(),
        })
    return [r for r in result if r["hasIndex"]]


@router.get("/config")
def get_tutorials_config():
    """Return the effective output directory used for listing/serving tutorials (from OUTPUT_DIR env)."""
    return {"output_dir": str(_OUTPUT_DIR)}


@router.get("/{tutorial_path:path}")
def get_tutorial_file(tutorial_path: str):
    """
    Serve a file from the output directory. Path is relative to OUTPUT_DIR (e.g. pvc-cdp/index.md).
    Path traversal (..) is not allowed.
    """
    if not _OUTPUT_DIR.is_dir():
        raise HTTPException(status_code=404, detail="Output directory not available.")
    path = _safe_relative_path(_OUTPUT_DIR, tutorial_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    content_type = _CONTENT_TYPES.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=content_type, filename=path.name)
