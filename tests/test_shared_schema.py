"""Unit tests for shared store schema and defaults."""

import pytest

from shared_schema import default_shared_store


def test_default_shared_store_has_all_required_keys():
    """Default shared store must contain all keys used by nodes."""
    shared = default_shared_store()
    required = [
        "repo_url",
        "local_dir",
        "project_name",
        "github_token",
        "output_dir",
        "include_patterns",
        "exclude_patterns",
        "max_file_size",
        "language",
        "files",
        "abstractions",
        "relationships",
        "chapter_order",
        "chapters",
        "final_output_dir",
    ]
    for key in required:
        assert key in shared, f"Missing key: {key}"


def test_default_shared_store_types():
    """Default values must have correct types."""
    shared = default_shared_store()
    assert shared["repo_url"] is None or isinstance(shared["repo_url"], str)
    assert shared["local_dir"] is None or isinstance(shared["local_dir"], str)
    assert shared["output_dir"] == "output"
    assert isinstance(shared["include_patterns"], set)
    assert isinstance(shared["exclude_patterns"], set)
    assert shared["max_file_size"] == 100_000
    assert shared["language"] == "english"
    assert shared["files"] == []
    assert shared["abstractions"] == []
    assert shared["relationships"]["summary"] is None
    assert shared["relationships"]["details"] == []
    assert shared["chapter_order"] == []
    assert shared["chapters"] == []
    assert shared["final_output_dir"] is None


def test_default_shared_store_structure_relationships():
    """relationships must be a dict with 'summary' and 'details'."""
    shared = default_shared_store()
    assert "summary" in shared["relationships"]
    assert "details" in shared["relationships"]
    assert isinstance(shared["relationships"]["details"], list)


def test_default_shared_store_returns_new_copy():
    """Each call returns a new dict; mutating one does not affect another."""
    a = default_shared_store()
    b = default_shared_store()
    a["files"].append(("x", "y"))
    assert len(b["files"]) == 0
    a["include_patterns"].add("*.py")
    assert len(b["include_patterns"]) == 0
