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
        mock_run.side_effect = lambda sh: sh.update({
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
        mock_run.side_effect = lambda sh: sh.update({
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
    with patch("api.runner._run_flow") as mock_run:
        import time
        def slow(_):
            time.sleep(2)
        mock_run.side_effect = slow
        resp = client.post("/v1/jobs", json={"repo_url": "https://github.com/owner/repo"})
    job_id = resp.json()["job_id"]
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
        mock_run.side_effect = lambda sh: sh.update({
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
        mock_run.side_effect = lambda sh: sh.update({
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
