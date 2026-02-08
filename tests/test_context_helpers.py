"""Unit tests for context_helpers: create_llm_context, get_content_for_indices."""

import pytest

from utils.context_helpers import create_llm_context, get_content_for_indices


def test_create_llm_context_formats_index_path_per_line():
    """create_llm_context returns one line per file: index # path."""
    files = [
        ("src/main.py", "print(1)"),
        ("src/utils.py", "def foo(): pass"),
    ]
    result = create_llm_context(files)
    assert result == "0 # src/main.py\n1 # src/utils.py"


def test_create_llm_context_empty_list():
    """create_llm_context with empty files returns empty string."""
    assert create_llm_context([]) == ""


def test_create_llm_context_single_file():
    """create_llm_context with one file returns single line."""
    files = [("readme.md", "hi")]
    assert create_llm_context(files) == "0 # readme.md"


def test_get_content_for_indices_returns_content_for_each_index():
    """get_content_for_indices returns formatted content for given indices."""
    files = [
        ("a.py", "code_a"),
        ("b.py", "code_b"),
        ("c.py", "code_c"),
    ]
    result = get_content_for_indices(files, [0, 2])
    assert "0 # a.py\ncode_a" in result
    assert "2 # c.py\ncode_c" in result
    assert "code_b" not in result
    assert result.count("\n\n") >= 1


def test_get_content_for_indices_skips_invalid_indices():
    """get_content_for_indices skips indices out of range."""
    files = [("x.py", "x")]
    result = get_content_for_indices(files, [0, 5, -1])
    assert "0 # x.py\nx" in result
    assert "5 #" not in result
    assert "-1 #" not in result


def test_get_content_for_indices_empty_indices():
    """get_content_for_indices with empty indices returns empty string."""
    files = [("a.py", "a")]
    assert get_content_for_indices(files, []) == ""


def test_get_content_for_indices_empty_files():
    """get_content_for_indices with empty files returns empty string."""
    assert get_content_for_indices([], [0, 1]) == ""
