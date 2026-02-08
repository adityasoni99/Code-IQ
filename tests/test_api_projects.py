"""Tests for project API: create from job, PATCH, regenerate."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api import job_store, project_store
from api.app import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_stores():
    job_store._store.clear()
    project_store._store.clear()
    yield
    job_store._store.clear()
    project_store._store.clear()


def test_create_project_from_job_404_when_job_missing(client):
    """POST /v1/projects/from-job/{id} returns 404 when job not found."""
    r = client.post("/v1/projects/from-job/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_create_project_from_job_400_when_not_completed(client):
    """POST /v1/projects/from-job/{id} returns 400 when job not completed."""
    import time
    with patch("api.runner._run_flow") as mock_run:
        def slow(_):
            time.sleep(5)
        mock_run.side_effect = slow
        r = client.post("/v1/jobs", json={"repo_url": "https://github.com/owner/repo"})
    assert r.status_code == 201
    job_id = r.json()["job_id"]
    rp = client.post(f"/v1/projects/from-job/{job_id}")
    assert rp.status_code == 400


def test_create_project_from_job_201_and_patch(client):
    """Create project from completed job; PATCH updates summary."""
    with patch("api.runner._run_flow") as mock_run:
        mock_run.side_effect = lambda sh: sh.update({
            "final_output_dir": "/tmp/out",
            "relationships": {"summary": "Old summary."},
            "chapters": ["# Ch1"],
            "abstractions": [{"name": "Ch1"}],
            "chapter_order": [0],
        })
        r = client.post("/v1/jobs", json={"repo_url": "https://github.com/owner/repo"})
    assert r.status_code == 201
    job_id = r.json()["job_id"]
    for _ in range(30):
        rj = client.get(f"/v1/jobs/{job_id}")
        if rj.status_code == 200 and rj.json().get("status") == "completed":
            break
    else:
        pytest.fail("Job did not complete")
    rp = client.post(f"/v1/projects/from-job/{job_id}")
    assert rp.status_code == 201
    data = rp.json()
    assert "project_id" in data
    assert data["summary"] == "Old summary."
    project_id = data["project_id"]
    rpatch = client.patch(f"/v1/projects/{project_id}", json={"summary": "New summary."})
    assert rpatch.status_code == 200
    assert rpatch.json()["summary"] == "New summary."


def test_regenerate_202(client):
    """POST /v1/projects/{id}/regenerate returns 202 with job_id."""
    with patch("api.runner._run_flow") as mock_run:
        mock_run.side_effect = lambda sh: sh.update({
            "final_output_dir": "/tmp/out",
            "relationships": {"summary": "S."},
            "chapters": ["# Ch1"],
            "abstractions": [{"name": "Ch1"}],
            "chapter_order": [0],
        })
        r = client.post("/v1/jobs", json={"repo_url": "https://github.com/owner/repo"})
    job_id = r.json()["job_id"]
    for _ in range(30):
        if client.get(f"/v1/jobs/{job_id}").json().get("status") == "completed":
            break
    rp = client.post(f"/v1/projects/from-job/{job_id}")
    assert rp.status_code == 201
    project_id = rp.json()["project_id"]
    rreg = client.post(f"/v1/projects/{project_id}/regenerate", json={"scope": "full"})
    assert rreg.status_code == 202
    assert "job_id" in rreg.json()
