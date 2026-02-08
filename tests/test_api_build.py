"""Tests for sync build API: POST /v1/build."""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.app import app


@pytest.fixture
def client():
    """Sync test client for the FastAPI app."""
    return TestClient(app)


def test_build_400_when_no_repo_url(client):
    """Require repo_url; return 400 when missing."""
    resp = client.post("/v1/build", json={})
    assert resp.status_code == 400
    detail = resp.json().get("detail", "").lower()
    assert "repo_url" in detail or "provide" in detail


def test_build_400_when_repo_url_empty(client):
    """Require non-empty repo_url."""
    resp = client.post("/v1/build", json={"repo_url": "   "})
    assert resp.status_code == 400


def test_build_200_with_mocked_flow(client):
    """On success return 200 with final_output_dir and optional summary."""
    def fake_run(shared):
        shared["final_output_dir"] = "/tmp/out/my_project"
        shared["relationships"] = {"summary": "A great project."}

    with patch("api.routes.v1.build._run_flow_sync") as mock_run:
        mock_run.side_effect = fake_run
        resp = client.post(
            "/v1/build",
            json={"repo_url": "https://github.com/owner/repo"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["final_output_dir"] == "/tmp/out/my_project"
    assert data["summary"] == "A great project."


def test_build_413_when_timeout(client):
    """When flow exceeds max duration return 413."""
    import api.routes.v1.build as build_module

    original_timeout = build_module.BUILD_TIMEOUT_SECONDS
    build_module.BUILD_TIMEOUT_SECONDS = 0  # timeout immediately

    def slow_run(_shared):
        time.sleep(2)  # longer than 0s timeout

    try:
        with patch("api.routes.v1.build._run_flow_sync", side_effect=slow_run):
            resp = client.post(
                "/v1/build",
                json={"repo_url": "https://github.com/owner/repo"},
            )
        assert resp.status_code == 413
        assert "exceeded" in resp.json().get("detail", "").lower()
    finally:
        build_module.BUILD_TIMEOUT_SECONDS = original_timeout
