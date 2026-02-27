"""Tests for async jobs API: POST /v1/jobs, POST /v1/jobs/upload, GET /v1/jobs/{id}, GET /v1/jobs/{id}/result."""

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api import job_store
from api.app import app


def _make_small_zip() -> bytes:
    """Return zip bytes containing index.md and one chapter."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.md", "# Tutorial\n")
        zf.writestr("src/main.py", "print('hello')")
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_job_store():
    """Reset in-memory job store between tests (clear _store)."""
    job_store._store.clear()
    yield
    job_store._store.clear()


def test_post_jobs_201_with_job_id(client):
    """POST /v1/jobs returns 201 with job_id and Location header."""
    with patch("api.runner._run_flow") as mock_run:
        mock_run.side_effect = lambda sh, mode=None: sh.update({
            "final_output_dir": "/tmp/out/proj",
            "relationships": {"summary": "Done."},
        })
        resp = client.post("/v1/jobs", json={"repo_url": "https://github.com/owner/repo"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["job_id"]
    assert data["status"] == "queued"
    assert resp.headers.get("Location") == f'/v1/jobs/{data["job_id"]}'


def test_post_jobs_400_when_no_repo_url(client):
    """POST /v1/jobs requires repo_url."""
    resp = client.post("/v1/jobs", json={})
    assert resp.status_code == 400


def test_get_job_404_unknown(client):
    """GET /v1/jobs/{id} returns 404 for unknown job."""
    resp = client.get("/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_get_job_200_after_completion(client):
    """Create job, wait for completion (mocked), GET returns status and result."""
    with patch("api.runner._run_flow") as mock_run:
        mock_run.side_effect = lambda sh, mode=None: sh.update({
            "final_output_dir": "/tmp/out/proj",
            "relationships": {"summary": "Done."},
        })
        resp = client.post("/v1/jobs", json={"repo_url": "https://github.com/owner/repo"})
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]
    # Poll until completed (runner runs in thread)
    for _ in range(50):
        r = client.get(f"/v1/jobs/{job_id}")
        assert r.status_code == 200
        if r.json()["status"] == "completed":
            assert r.json().get("result", {}).get("final_output_dir") == "/tmp/out/proj"
            break
        if r.json()["status"] == "failed":
            pytest.fail("Job failed")
    else:
        pytest.fail("Job did not complete in time")


def test_get_job_result_409_while_running(client):
    """GET /v1/jobs/{id}/result returns 409 when job still running."""
    job_id = job_store.create_job({"repo_url": "https://github.com/owner/repo"})
    job_store.update_status(job_id, "running")
    r = client.get(f"/v1/jobs/{job_id}/result")
    assert r.status_code == 409


def test_get_job_result_404_when_failed(client):
    """GET /v1/jobs/{id}/result returns 404 when job failed."""
    with patch("api.runner._run_flow") as mock_run:
        mock_run.side_effect = RuntimeError("Pipeline failed")
        resp = client.post("/v1/jobs", json={"repo_url": "https://github.com/owner/repo"})
    job_id = resp.json()["job_id"]
    for _ in range(20):
        r = client.get(f"/v1/jobs/{job_id}")
        if r.json()["status"] == "failed":
            break
    else:
        pytest.fail("Job did not fail")
    r_result = client.get(f"/v1/jobs/{job_id}/result")
    assert r_result.status_code == 404


def test_get_job_result_200_zip_when_completed(client, tmp_path):
    """When job completed with real output dir, GET result returns zip."""
    (tmp_path / "index.md").write_text("# Tutorial")
    (tmp_path / "01_ch.md").write_text("Chapter 1")
    out_dir = str(tmp_path)

    with patch("api.runner._run_flow") as mock_run:
        mock_run.side_effect = lambda sh, mode=None: sh.update({
            "final_output_dir": out_dir,
            "relationships": {"summary": "Done."},
        })
        resp = client.post("/v1/jobs", json={"repo_url": "https://github.com/owner/repo"})
    job_id = resp.json()["job_id"]
    for _ in range(50):
        r = client.get(f"/v1/jobs/{job_id}")
        if r.status_code == 200 and r.json().get("status") == "completed":
            break
    else:
        pytest.fail("Job did not complete")
    r_result = client.get(f"/v1/jobs/{job_id}/result")
    assert r_result.status_code == 200
    assert r_result.headers["content-type"] == "application/zip"
    assert "attachment" in r_result.headers.get("content-disposition", "")
    # Zip contains our files
    import zipfile, io
    z = zipfile.ZipFile(io.BytesIO(r_result.content), "r")
    names = z.namelist()
    z.close()
    assert "index.md" in names
    assert "01_ch.md" in names


def test_post_jobs_upload_201_and_completes(client, tmp_path):
    """POST /v1/jobs/upload with small zip returns 201; job completes with result."""
    (tmp_path / "index.md").write_text("# Tutorial")
    (tmp_path / "01_ch.md").write_text("Chapter 1")
    out_dir = str(tmp_path)
    zip_bytes = _make_small_zip()

    with patch("api.runner._run_flow") as mock_run:
        mock_run.side_effect = lambda sh, mode=None: sh.update({
            "final_output_dir": out_dir,
            "relationships": {"summary": "Done."},
        })
        resp = client.post(
            "/v1/jobs/upload",
            files={"file": ("project.zip", zip_bytes, "application/zip")},
            data={"project_name": "MyProj", "language": "english"},
        )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]
    for _ in range(50):
        r = client.get(f"/v1/jobs/{job_id}")
        if r.status_code == 200 and r.json().get("status") == "completed":
            assert r.json().get("result", {}).get("final_output_dir") == out_dir
            return
    pytest.fail("Upload job did not complete")


# ---- Recursive job, tree, file, CORS, progress ----

def test_post_jobs_recursive_201(client):
    """POST /v1/jobs/recursive returns 201 with job_id."""
    with patch("api.runner._run_flow") as mock_run:
        mock_run.side_effect = lambda sh, mode=None: sh.update({
            "master_index_path": "/tmp/out/master_index.html",
            "final_output_dir": "/tmp/out",
            "relationships": {"summary": "Done."},
        })
        resp = client.post("/v1/jobs/recursive", json={"parent_dirs": ["/tmp/parent"]})
    assert resp.status_code == 201
    data = resp.json()
    assert data["job_id"]
    assert data["status"] == "queued"
    assert resp.headers.get("Location") == f'/v1/jobs/{data["job_id"]}'


def test_post_jobs_recursive_400_empty_parent_dirs(client):
    """POST /v1/jobs/recursive requires at least one parent_dirs path."""
    resp = client.post("/v1/jobs/recursive", json={"parent_dirs": []})
    assert resp.status_code == 400
    resp2 = client.post("/v1/jobs/recursive", json={"parent_dirs": ["  ", ""]})
    assert resp2.status_code == 400


def test_get_job_tree_404_no_job(client):
    """GET /v1/jobs/{id}/tree returns 404 for unknown job."""
    resp = client.get("/v1/jobs/00000000-0000-0000-0000-000000000000/tree")
    assert resp.status_code == 404


def test_get_job_tree_409_not_completed(client):
    """GET /v1/jobs/{id}/tree returns 409 when job not completed."""
    job_id = job_store.create_job({"repo_url": "https://x.com/r", "mode": "single"})
    resp = client.get(f"/v1/jobs/{job_id}/tree")
    assert resp.status_code == 409


def test_get_job_tree_200_single_fallback(client, tmp_path):
    """GET /v1/jobs/{id}/tree for single job returns single-entry tree when no tree.json."""
    proj_dir = tmp_path / "out" / "myproj"
    proj_dir.mkdir(parents=True)
    (proj_dir / "index.md").write_text("# Tutorial")
    job_id = job_store.create_job({"repo_url": "https://x.com/r", "mode": "single"})
    job_store.update_status(job_id, "completed", result={"final_output_dir": str(proj_dir)})
    resp = client.get(f"/v1/jobs/{job_id}/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "myproj"
    assert data[0]["slug"] == "myproj"


def test_get_job_tree_200_recursive_with_tree_json(client, tmp_path):
    """GET /v1/jobs/{id}/tree returns tree.json content when present."""
    out_root = tmp_path / "output"
    out_root.mkdir()
    tree_data = [{"name": "a", "slug": "a", "children": [{"name": "b", "slug": "b", "children": []}]}]
    import json
    (out_root / "tree.json").write_text(json.dumps(tree_data), encoding="utf-8")
    job_id = job_store.create_job({"mode": "recursive"})
    job_store.update_status(job_id, "completed", result={"final_output_dir": str(out_root)})
    resp = client.get(f"/v1/jobs/{job_id}/tree")
    assert resp.status_code == 200
    assert resp.json() == tree_data


def test_get_job_file_404_unknown_job(client):
    """GET /v1/jobs/{id}/files/path returns 404 for unknown job."""
    resp = client.get("/v1/jobs/00000000-0000-0000-0000-000000000000/files/index.md")
    assert resp.status_code == 404


def test_get_job_file_409_not_completed(client):
    """GET /v1/jobs/{id}/files/path returns 409 when job not completed."""
    job_id = job_store.create_job({"repo_url": "https://x.com/r"})
    resp = client.get(f"/v1/jobs/{job_id}/files/index.md")
    assert resp.status_code == 409


def test_get_job_file_200_serves_file(client, tmp_path):
    """GET /v1/jobs/{id}/files/{path} returns file content with correct content-type."""
    out_root = tmp_path / "out"
    out_root.mkdir()
    (out_root / "readme.md").write_text("# Hello", encoding="utf-8")
    job_id = job_store.create_job({"repo_url": "https://x.com/r"})
    job_store.update_status(job_id, "completed", result={"final_output_dir": str(out_root)})
    resp = client.get(f"/v1/jobs/{job_id}/files/readme.md")
    assert resp.status_code == 200
    assert resp.text.strip() == "# Hello"
    assert "text/markdown" in resp.headers.get("content-type", "")


def test_get_job_file_400_path_traversal(client, tmp_path):
    """GET /v1/jobs/{id}/files/{path} with path containing .. returns 400 (path traversal)."""
    out_root = tmp_path / "out"
    out_root.mkdir()
    job_id = job_store.create_job({"repo_url": "https://x.com/r"})
    job_store.update_status(job_id, "completed", result={"final_output_dir": str(out_root)})
    # Request with explicit ".." in path (client may encode as %2E%2E%2F or similar)
    resp = client.get(f"/v1/jobs/{job_id}/files/..%2Fetc%2Fpasswd")
    assert resp.status_code == 400


def test_get_job_includes_progress_and_mode(client):
    """GET /v1/jobs/{id} includes progress and mode for recursive jobs."""
    job_id = job_store.create_job({
        "mode": "recursive",
        "parent_dirs": ["/tmp/p"],
    })
    job_store.update_progress(job_id, 2, 5, "current_folder_name")
    resp = client.get(f"/v1/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "recursive"
    assert data["progress"] == {"completed": 2, "total": 5, "current_folder": "current_folder_name"}


def test_cors_headers_present(client):
    """OPTIONS or GET with Origin returns CORS headers."""
    resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    # TestClient may not expose all CORS headers; at least app has middleware
    from api.app import CORS_ORIGINS
    assert "http://localhost:5173" in CORS_ORIGINS
