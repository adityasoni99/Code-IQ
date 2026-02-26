"""Unit tests for utils.dir_helpers."""

import os
from pathlib import Path

import pytest

from utils.dir_helpers import (
    CHECKPOINT_MARKER,
    count_files_under,
    get_direct_subdirs,
    has_direct_subdirs,
    is_completed,
)


def test_count_files_under_empty_dir(tmp_path):
    """Empty directory returns 0."""
    assert count_files_under(tmp_path) == 0


def test_count_files_under_nested_files(tmp_path):
    """Directory with 3 files (nested) returns 3."""
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("")
    (tmp_path / "sub" / "c.txt").write_text("")
    assert count_files_under(tmp_path) == 3


def test_count_files_under_subdirs_only_no_files(tmp_path):
    """Directory with subdirectories only (no files) returns 0."""
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub2").mkdir()
    assert count_files_under(tmp_path) == 0


def test_count_files_under_nonexistent_returns_zero():
    """Handles non-existent path gracefully (returns 0 via OSError catch)."""
    assert count_files_under(Path("/nonexistent/path/xyz")) == 0


def test_has_direct_subdirs_true_when_visible_subdir(tmp_path):
    """Returns True when directory has a visible subdirectory."""
    (tmp_path / "visible").mkdir()
    assert has_direct_subdirs(tmp_path) is True


def test_has_direct_subdirs_false_flat_files_only(tmp_path):
    """Returns False for a flat directory with files only."""
    (tmp_path / "f1.txt").write_text("")
    (tmp_path / "f2.txt").write_text("")
    assert has_direct_subdirs(tmp_path) is False


def test_has_direct_subdirs_skip_hidden_true_ignores_hidden(tmp_path):
    """skip_hidden=True (default): ignores .hidden dirs, returns False if only hidden subdirs exist."""
    (tmp_path / ".hidden").mkdir()
    assert has_direct_subdirs(tmp_path, skip_hidden=True) is False


def test_has_direct_subdirs_skip_hidden_false_includes_hidden(tmp_path):
    """skip_hidden=False: includes .hidden dirs, returns True if hidden subdirs exist."""
    (tmp_path / ".hidden").mkdir()
    assert has_direct_subdirs(tmp_path, skip_hidden=False) is True


def test_get_direct_subdirs_sorted(tmp_path):
    """Returns sorted list of direct subdirectory Paths."""
    (tmp_path / "c").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    result = get_direct_subdirs(tmp_path, skip_hidden=True)
    assert result == [tmp_path / "a", tmp_path / "b", tmp_path / "c"]


def test_get_direct_subdirs_skip_hidden_true_excludes_dot(tmp_path):
    """skip_hidden=True: excludes directories starting with '.'."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "visible").mkdir()
    result = get_direct_subdirs(tmp_path, skip_hidden=True)
    assert result == [tmp_path / "visible"]


def test_get_direct_subdirs_skip_hidden_false_includes_dot(tmp_path):
    """skip_hidden=False: includes directories starting with '.'."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "visible").mkdir()
    result = get_direct_subdirs(tmp_path, skip_hidden=False)
    assert len(result) == 2
    assert tmp_path / ".hidden" in result
    assert tmp_path / "visible" in result


def test_get_direct_subdirs_empty(tmp_path):
    """Returns empty list for a directory with no subdirectories."""
    (tmp_path / "file.txt").write_text("")
    assert get_direct_subdirs(tmp_path, skip_hidden=True) == []


def test_is_completed_true_when_index_md_exists(tmp_path):
    """Returns True when output_dir/project_name/index.md exists."""
    out = tmp_path / "proj"
    out.mkdir()
    (out / "index.md").write_text("# Tutorial")
    assert is_completed(tmp_path, "proj") is True


def test_is_completed_false_when_no_file(tmp_path):
    """Returns False when the file does not exist."""
    assert is_completed(tmp_path, "proj") is False


def test_is_completed_false_when_dir_exists_but_no_index_md(tmp_path):
    """Returns False when output_dir/project_name/ exists but index.md is missing."""
    (tmp_path / "proj").mkdir()
    assert is_completed(tmp_path, "proj") is False


def test_checkpoint_marker_constant():
    """CHECKPOINT_MARKER is index.md."""
    assert CHECKPOINT_MARKER == "index.md"
