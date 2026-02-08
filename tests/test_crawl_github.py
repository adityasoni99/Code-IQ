"""Unit tests for crawl_github_files."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from utils.crawl_github_files import _parse_repo_url, crawl_github_files


def test_parse_repo_url_https():
    """Parse https://github.com/owner/repo."""
    assert _parse_repo_url("https://github.com/owner/repo") == ("owner", "repo")
    assert _parse_repo_url("https://github.com/owner/repo/") == ("owner", "repo")
    assert _parse_repo_url("https://github.com/owner/repo.git") == ("owner", "repo")


def test_parse_repo_url_ssh():
    """Parse git@github.com:owner/repo.git."""
    assert _parse_repo_url("git@github.com:owner/repo.git") == ("owner", "repo")
    assert _parse_repo_url("git@github.com:owner/repo") == ("owner", "repo")


def test_parse_repo_url_invalid():
    """Invalid URL raises ValueError."""
    with pytest.raises(ValueError, match="Cannot parse"):
        _parse_repo_url("not-a-url")
    with pytest.raises(ValueError, match="Cannot parse"):
        _parse_repo_url("https://gitlab.com/owner/repo")


def test_crawl_github_files_contract():
    """Return value has 'files' (dict) and 'stats' (dict) with expected keys."""
    with patch("utils.crawl_github_files.requests.get") as mock_get:
        resp_repo = MagicMock()
        resp_repo.json.return_value = {"default_branch": "main"}
        resp_tree = MagicMock()
        resp_tree.json.return_value = {"tree": [], "truncated": False}
        mock_get.side_effect = [resp_repo, resp_tree]
        result = crawl_github_files("https://github.com/owner/repo")
    assert "files" in result
    assert "stats" in result
    assert isinstance(result["files"], dict)
    assert isinstance(result["stats"], dict)
    assert result["stats"]["files_count"] == 0
    assert "skipped_size" in result["stats"]
    assert "skipped_pattern" in result["stats"]
    assert "skipped_decode" in result["stats"]
    assert "truncated" in result["stats"]


def test_crawl_github_files_mock_tree_with_blobs():
    """With mocked API returning one blob, files dict gets one entry."""
    with patch("utils.crawl_github_files.requests.get") as mock_get:
        resp_repo = MagicMock()
        resp_repo.json.return_value = {"default_branch": "main"}
        resp_tree = MagicMock()
        resp_tree.json.return_value = {
            "tree": [{"type": "blob", "path": "readme.md", "size": 10, "sha": "abc123"}],
            "truncated": False,
        }
        resp_blob = MagicMock()
        resp_blob.json.return_value = {"content": "aGVsbG8=", "encoding": "base64"}  # "hello"
        mock_get.side_effect = [resp_repo, resp_tree, resp_blob]
        result = crawl_github_files("https://github.com/owner/repo")
    assert result["files"].get("readme.md") == "hello"
    assert result["stats"]["files_count"] == 1


def test_crawl_github_files_skips_large_blobs():
    """Blobs over max_file_size are skipped (no blob fetch)."""
    with patch("utils.crawl_github_files.requests.get") as mock_get:
        resp_repo = MagicMock()
        resp_repo.json.return_value = {"default_branch": "main"}
        resp_tree = MagicMock()
        resp_tree.json.return_value = {
            "tree": [{"type": "blob", "path": "big.py", "size": 200_000, "sha": "x"}],
            "truncated": False,
        }
        mock_get.side_effect = [resp_repo, resp_tree]
        result = crawl_github_files("https://github.com/owner/repo", max_file_size=100_000)
    assert len(result["files"]) == 0
    assert result["stats"]["skipped_size"] == 1


def test_crawl_github_files_include_patterns():
    """With include_patterns only matching paths are fetched."""
    with patch("utils.crawl_github_files.requests.get") as mock_get:
        resp_repo = MagicMock()
        resp_repo.json.return_value = {"default_branch": "main"}
        resp_tree = MagicMock()
        resp_tree.json.return_value = {
            "tree": [
                {"type": "blob", "path": "a.py", "size": 5, "sha": "s1"},
                {"type": "blob", "path": "b.txt", "size": 5, "sha": "s2"},
            ],
            "truncated": False,
        }
        resp_blob = MagicMock()
        resp_blob.json.return_value = {"content": "Y29kZQ==", "encoding": "base64"}  # "code"
        mock_get.side_effect = [resp_repo, resp_tree, resp_blob]
        result = crawl_github_files(
            "https://github.com/o/r",
            include_patterns={"*.py"},
        )
    assert "a.py" in result["files"]
    assert result["files"]["a.py"] == "code"
    assert "b.txt" not in result["files"]
    assert result["stats"]["skipped_pattern"] == 1


def test_crawl_github_files_403_rate_limit_raises_helpful_error():
    """On 403 rate limit after retries, raise error suggesting GITHUB_TOKEN."""
    with patch("utils.crawl_github_files.requests.get") as mock_get, patch(
        "utils.crawl_github_files.time.sleep"
    ) as _:
        resp_repo = MagicMock()
        resp_repo.json.return_value = {"default_branch": "main"}
        resp_tree = MagicMock()
        resp_tree.json.return_value = {
            "tree": [{"type": "blob", "path": "x.py", "size": 5, "sha": "s1"}],
            "truncated": False,
        }
        resp_403 = MagicMock()
        resp_403.status_code = 403
        resp_403.text = "rate limit exceeded"
        mock_get.side_effect = [resp_repo, resp_tree, resp_403, resp_403, resp_403]
        with pytest.raises(requests.HTTPError) as exc_info:
            crawl_github_files("https://github.com/o/r")
        assert "GITHUB_TOKEN" in str(exc_info.value)
