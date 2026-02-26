"""Unit tests for DiscoverLeafFolders node."""

from pathlib import Path

import pytest

from nodes import DiscoverLeafFolders


def test_flat_directory_two_subdirs_parent_last(tmp_path):
    """Flat directory (no recursion): 2 subdirs + parent → output has 3 entries, parent is last."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "f.txt").write_text("")
    (tmp_path / "b" / "g.txt").write_text("")
    shared = {
        "parent_dirs": [str(tmp_path)],
        "file_threshold": 100,
        "skip_hidden": True,
        "resume": True,
        "output_dir": str(tmp_path / "out"),
    }
    node = DiscoverLeafFolders()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    node.post(shared, prep_res, exec_res)
    assert len(exec_res) == 3
    names = [e["project_name"] for e in exec_res]
    assert "a" in names and "b" in names and tmp_path.name in names
    assert exec_res[-1]["project_name"] == tmp_path.name
    assert shared["leaf_folders"] == exec_res


def test_nested_directory_threshold_recursion(tmp_path):
    """Nested dir: parent has subdir A (150 files, has sub-subdirs) and B (50 files, no subdirs).
    Verify A is recursed (its children are leaves), B is direct leaf, parent is last."""
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    for i in range(150):
        (tmp_path / "A" / f"f{i}.txt").write_text("")
    (tmp_path / "A" / "sub1").mkdir()
    (tmp_path / "A" / "sub2").mkdir()
    for i in range(30):
        (tmp_path / "A" / "sub1" / f"g{i}.txt").write_text("")
    for i in range(30):
        (tmp_path / "A" / "sub2" / f"h{i}.txt").write_text("")
    for i in range(50):
        (tmp_path / "B" / f"b{i}.txt").write_text("")
    out_base = tmp_path / "out"
    shared = {
        "parent_dirs": [str(tmp_path)],
        "file_threshold": 100,
        "skip_hidden": True,
        "resume": True,
        "output_dir": str(out_base),
    }
    node = DiscoverLeafFolders()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    project_names = [e["project_name"] for e in exec_res]
    # Leaves: sub1, sub2 (under A), B, then parent
    assert "sub1" in project_names
    assert "sub2" in project_names
    assert "B" in project_names
    assert exec_res[-1]["project_name"] == tmp_path.name


def test_checkpoint_resume_skips_done(tmp_path):
    """Checkpoint/resume: create fake output_dir/parent_name/project_name/index.md; verify folder is skipped when resume=True."""
    (tmp_path / "done_dir").mkdir()
    (tmp_path / "done_dir" / "f.txt").write_text("")
    out_base = tmp_path / "out"
    # Checkpoint path is output_dir / parent.name / project_name / index.md
    (out_base / tmp_path.name / "done_dir").mkdir(parents=True)
    (out_base / tmp_path.name / "done_dir" / "index.md").write_text("# Done")
    shared = {
        "parent_dirs": [str(tmp_path)],
        "file_threshold": 100,
        "skip_hidden": True,
        "resume": True,
        "output_dir": str(out_base),
    }
    node = DiscoverLeafFolders()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    names = [e["project_name"] for e in exec_res]
    assert "done_dir" not in names
    assert tmp_path.name in names


def test_no_resume_includes_all(tmp_path):
    """resume=False: all folders included even with existing index.md."""
    (tmp_path / "done_dir").mkdir()
    (tmp_path / "done_dir" / "f.txt").write_text("")
    out_base = tmp_path / "out"
    (out_base / "done_dir").mkdir(parents=True)
    (out_base / "done_dir" / "index.md").write_text("# Done")
    shared = {
        "parent_dirs": [str(tmp_path)],
        "file_threshold": 100,
        "skip_hidden": True,
        "resume": False,
        "output_dir": str(out_base),
    }
    node = DiscoverLeafFolders()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    names = [e["project_name"] for e in exec_res]
    assert "done_dir" in names
    assert exec_res[-1]["project_name"] == tmp_path.name


def test_parent_folder_last_ordering(tmp_path):
    """Parent-folder-last: last entry is always the parent directory."""
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f.txt").write_text("")
    shared = {
        "parent_dirs": [str(tmp_path)],
        "file_threshold": 100,
        "skip_hidden": True,
        "resume": True,
        "output_dir": str(tmp_path / "out"),
    }
    node = DiscoverLeafFolders()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    assert exec_res[-1]["project_name"] == tmp_path.name
    assert exec_res[-1]["local_dir"] == str(tmp_path.resolve())


def test_skip_hidden_excluded(tmp_path):
    """skip_hidden=True: hidden subdirectory .hidden excluded."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "f.txt").write_text("")
    (tmp_path / "visible").mkdir()
    (tmp_path / "visible" / "g.txt").write_text("")
    shared = {
        "parent_dirs": [str(tmp_path)],
        "file_threshold": 100,
        "skip_hidden": True,
        "resume": True,
        "output_dir": str(tmp_path / "out"),
    }
    node = DiscoverLeafFolders()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    names = [e["project_name"] for e in exec_res]
    assert ".hidden" not in names
    assert "visible" in names


def test_skip_hidden_false_includes_hidden(tmp_path):
    """skip_hidden=False: .hidden included."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "f.txt").write_text("")
    shared = {
        "parent_dirs": [str(tmp_path)],
        "file_threshold": 100,
        "skip_hidden": False,
        "resume": True,
        "output_dir": str(tmp_path / "out"),
    }
    node = DiscoverLeafFolders()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    names = [e["project_name"] for e in exec_res]
    assert ".hidden" in names
    assert exec_res[-1]["project_name"] == tmp_path.name


def test_empty_directory_returns_only_parent(tmp_path):
    """Empty directory: returns list containing only the parent itself."""
    shared = {
        "parent_dirs": [str(tmp_path)],
        "file_threshold": 100,
        "skip_hidden": True,
        "resume": True,
        "output_dir": str(tmp_path / "out"),
    }
    node = DiscoverLeafFolders()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    assert len(exec_res) == 1
    assert exec_res[0]["project_name"] == tmp_path.name
    assert exec_res[0]["local_dir"] == str(tmp_path.resolve())
