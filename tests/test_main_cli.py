"""Tests for main CLI: parse args, populate shared, exit codes."""

import sys
from unittest.mock import patch

import pytest

from main import main, parse_args


def test_parse_args_requires_repo_url_or_local_dir():
    """Parsing with neither --repo-url nor --local-dir raises (exit 2)."""
    with pytest.raises(SystemExit) as exc_info:
        parse_args([])
    assert exc_info.value.code != 0


def test_parse_args_with_local_dir():
    """Parse --local-dir and optional --project-name, --output-dir, --language."""
    args = parse_args(["--local-dir", "/path/to/code"])
    assert args.local_dir == "/path/to/code"
    assert args.repo_url is None
    assert args.project_name is None
    assert args.output_dir == "output"
    assert args.language == "english"

    args2 = parse_args([
        "--local-dir", ".",
        "--project-name", "MyApp",
        "--output-dir", "out",
        "--language", "spanish",
    ])
    assert args2.local_dir == "."
    assert args2.project_name == "MyApp"
    assert args2.output_dir == "out"
    assert args2.language == "spanish"


def test_parse_args_with_repo_url():
    """Parse --repo-url."""
    args = parse_args(["--repo-url", "https://github.com/o/r"])
    assert args.repo_url == "https://github.com/o/r"
    assert args.local_dir is None


def test_main_populates_shared_and_returns_0():
    """main() with valid args populates shared and returns 0 (flow mocked)."""
    with patch("main.create_full_flow") as mock_create:
        mock_flow = mock_create.return_value
        exit_code = main(["--local-dir", "/tmp/x"])
    assert exit_code == 0
    mock_flow.run.assert_called_once()
    shared = mock_flow.run.call_args[0][0]
    assert shared["local_dir"] == "/tmp/x"
    assert shared["repo_url"] is None
    assert shared["output_dir"] == "output"
    assert shared["language"] == "english"


def test_main_returns_nonzero_when_no_repo_or_local():
    """main() with neither --repo-url nor --local-dir exits non-zero."""
    exit_code = main([])
    assert exit_code != 0


def test_main_returns_1_on_flow_exception():
    """main() returns 1 when flow.run raises."""
    with patch("main.create_full_flow") as mock_create:
        mock_flow = mock_create.return_value
        mock_flow.run.side_effect = RuntimeError("fail")
        exit_code = main(["--local-dir", "/tmp/x"])
    assert exit_code == 1
