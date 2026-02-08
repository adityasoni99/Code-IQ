"""Unit tests for crawl_local_files."""

import os
import tempfile
from pathlib import Path

import pytest

from utils.crawl_local_files import crawl_local_files


def test_crawl_local_files_happy_path():
    """Crawl returns files dict with path -> content."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.txt").write_text("hello")
        (Path(tmp) / "b.txt").write_text("world")
        (Path(tmp) / "sub").mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "sub" / "c.txt").write_text("nested")
        result = crawl_local_files(tmp)
    assert "files" in result
    files = result["files"]
    assert len(files) == 3
    assert files["a.txt"] == "hello"
    assert files["b.txt"] == "world"
    assert files[os.path.join("sub", "c.txt")] == "nested"


def test_crawl_local_files_use_relative_paths_false():
    """With use_relative_paths=False, keys are absolute paths."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "x.txt").write_text("x")
        result = crawl_local_files(tmp, use_relative_paths=False)
    files = result["files"]
    assert len(files) == 1
    key = next(iter(files))
    assert os.path.isabs(key)
    assert key.endswith("x.txt")
    assert files[key] == "x"


def test_crawl_local_files_max_file_size():
    """Files larger than max_file_size are skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "small.txt").write_text("ok")
        (Path(tmp) / "big.txt").write_text("x" * 200)
        result = crawl_local_files(tmp, max_file_size=100)
    files = result["files"]
    assert len(files) == 1
    assert "small.txt" in files
    assert files["small.txt"] == "ok"


def test_crawl_local_files_include_patterns():
    """With include_patterns, only matching files are included."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.py").write_text("py")
        (Path(tmp) / "b.txt").write_text("txt")
        (Path(tmp) / "c.md").write_text("md")
        result = crawl_local_files(tmp, include_patterns={"*.py", "*.md"})
    files = result["files"]
    assert set(files.keys()) == {"a.py", "c.md"}
    assert files["a.py"] == "py"
    assert files["c.md"] == "md"


def test_crawl_local_files_exclude_patterns():
    """With exclude_patterns, matching files are excluded."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.py").write_text("py")
        (Path(tmp) / "b.pyc").write_text("bytecode")
        (Path(tmp) / "sub").mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "sub" / "x.pyc").write_text("x")
        result = crawl_local_files(tmp, exclude_patterns={"*.pyc"})
    files = result["files"]
    assert "a.py" in files
    assert "b.pyc" not in files
    assert os.path.join("sub", "x.pyc") not in files


def test_crawl_local_files_empty_directory():
    """Empty directory returns empty files dict."""
    with tempfile.TemporaryDirectory() as tmp:
        result = crawl_local_files(tmp)
    assert result["files"] == {}


def test_crawl_local_files_include_and_exclude():
    """include_patterns and exclude_patterns can be combined."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.py").write_text("a")
        (Path(tmp) / "test_a.py").write_text("test")
        result = crawl_local_files(
            tmp,
            include_patterns={"*.py"},
            exclude_patterns={"test_*"},
        )
    files = result["files"]
    assert "a.py" in files
    assert "test_a.py" not in files
