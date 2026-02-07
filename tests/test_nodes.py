"""Unit tests for nodes (FetchRepo prep/exec/post contract, shared store)."""

import os
from unittest.mock import patch

import pytest

from nodes import (
    AnalyzeRelationships,
    CombineTutorial,
    FetchRepo,
    IdentifyAbstractions,
    OrderChapters,
    WriteChapters,
    _derive_project_name,
    _extract_yaml_block,
    _parse_index_from_ref,
)


def test_derive_project_name_from_repo_url():
    """Project name is last segment of repo URL."""
    assert _derive_project_name("https://github.com/owner/repo", None, None) == "repo"
    assert _derive_project_name("https://github.com/a/b.git", None, None) == "b"


def test_derive_project_name_from_local_dir():
    """Project name is basename of local directory."""
    assert _derive_project_name(None, "/path/to/my_project", None) == "my_project"
    assert _derive_project_name(None, "/single", None) == "single"


def test_derive_project_name_existing_takes_precedence():
    """Existing project_name in shared is used when set."""
    assert _derive_project_name("https://github.com/o/r", None, "Custom") == "Custom"
    assert _derive_project_name(None, "/path/to/dir", "MyApp") == "MyApp"


def test_fetch_repo_prep_returns_dict_with_crawler_params():
    """FetchRepo.prep reads shared and returns params for exec."""
    shared = {
        "repo_url": None,
        "local_dir": "/tmp/code",
        "project_name": None,
        "github_token": None,
        "output_dir": "out",
        "include_patterns": set(),
        "exclude_patterns": set(),
        "max_file_size": 50_000,
    }
    node = FetchRepo()
    prep_res = node.prep(shared)
    assert prep_res["local_dir"] == "/tmp/code"
    assert prep_res["project_name"] == "code"
    assert prep_res["max_file_size"] == 50_000
    assert prep_res["use_relative_paths"] is True


def test_fetch_repo_exec_local_calls_crawl_local_and_returns_files_list_and_name():
    """FetchRepo.exec with local_dir calls crawl_local_files and returns (files_list, project_name)."""
    shared = {"local_dir": "/tmp/proj", "repo_url": None}
    node = FetchRepo()
    prep_res = node.prep(shared)
    with patch("nodes.crawl_local_files") as mock_crawl:
        mock_crawl.return_value = {"files": {"a.py": "code1", "b.py": "code2"}}
        exec_res = node.exec(prep_res)
    mock_crawl.assert_called_once()
    files_list, project_name = exec_res
    assert project_name == "proj"
    assert set(dict(files_list).keys()) == {"a.py", "b.py"}
    assert dict(files_list)["a.py"] == "code1"


def test_fetch_repo_exec_github_calls_crawl_github_and_returns_files_list_and_name():
    """FetchRepo.exec with repo_url calls crawl_github_files and returns (files_list, project_name)."""
    shared = {"repo_url": "https://github.com/owner/repo", "local_dir": None}
    node = FetchRepo()
    prep_res = node.prep(shared)
    with patch("nodes.crawl_github_files") as mock_crawl:
        mock_crawl.return_value = {"files": {"readme.md": "hi"}, "stats": {}}
        exec_res = node.exec(prep_res)
    mock_crawl.assert_called_once()
    files_list, project_name = exec_res
    assert project_name == "repo"
    assert dict(files_list) == {"readme.md": "hi"}


def test_fetch_repo_exec_raises_when_neither_repo_url_nor_local_dir():
    """FetchRepo.exec raises when both repo_url and local_dir are missing/empty."""
    shared = {"repo_url": None, "local_dir": None}
    node = FetchRepo()
    prep_res = node.prep(shared)
    with pytest.raises(ValueError, match="repo_url or local_dir"):
        node.exec(prep_res)


def test_fetch_repo_post_writes_files_and_project_name_to_shared():
    """FetchRepo.post writes files list and project_name to shared store."""
    shared = {}
    node = FetchRepo()
    prep_res = {}
    exec_res = ([("f1.py", "c1"), ("f2.py", "c2")], "my_project")
    action = node.post(shared, prep_res, exec_res)
    assert action == "default"
    assert shared["files"] == [("f1.py", "c1"), ("f2.py", "c2")]
    assert shared["project_name"] == "my_project"


def test_fetch_repo_run_integration_mock_local():
    """FetchRepo.run(shared) with mocked crawl_local populates shared['files'] and shared['project_name']."""
    shared = {"local_dir": "/tmp/example", "repo_url": None}
    node = FetchRepo()
    with patch("nodes.crawl_local_files") as mock_crawl:
        mock_crawl.return_value = {"files": {"x.txt": "content"}}
        action = node.run(shared)
    assert action == "default"
    assert shared["files"] == [("x.txt", "content")]
    assert shared["project_name"] == "example"


# --- IdentifyAbstractions ---


def test_parse_index_from_ref():
    """_parse_index_from_ref extracts int from '0 # path' or int."""
    assert _parse_index_from_ref("0 # src/main.py") == 0
    assert _parse_index_from_ref("1 # Flow") == 1
    assert _parse_index_from_ref(2) == 2


def test_extract_yaml_block():
    """_extract_yaml_block extracts content between ```yaml and ```."""
    text = "Here is the result:\n```yaml\n- name: X\n  files: [0]\n```"
    assert "name: X" in _extract_yaml_block(text)
    assert "```" not in _extract_yaml_block(text)


def test_identify_abstractions_prep_returns_file_context():
    """IdentifyAbstractions.prep builds file_context with create_llm_context."""
    shared = {
        "files": [("a.py", "c1"), ("b.py", "c2")],
        "project_name": "proj",
        "language": "english",
    }
    node = IdentifyAbstractions()
    prep_res = node.prep(shared)
    assert prep_res["file_context"] == "0 # a.py\n1 # b.py"
    assert prep_res["project_name"] == "proj"


def test_identify_abstractions_exec_parses_yaml_and_validates_indices():
    """IdentifyAbstractions.exec parses YAML and validates file indices (mock call_llm)."""
    prep_res = {
        "files": [("a.py", "x"), ("b.py", "y")],
        "project_name": "p",
        "language": "english",
        "file_context": "0 # a.py\n1 # b.py",
    }
    yaml_response = """
- name: Node
  description: A step in the pipeline.
  files: [0, 1]
- name: Flow
  description: Orchestrates nodes.
  files: [1]
"""
    with patch("nodes.call_llm", return_value=yaml_response):
        node = IdentifyAbstractions()
        result = node.exec(prep_res)
    assert len(result) == 2
    assert result[0]["name"] == "Node"
    assert result[0]["files"] == [0, 1]
    assert result[1]["name"] == "Flow"
    assert result[1]["files"] == [1]


def test_identify_abstractions_post_writes_abstractions():
    """IdentifyAbstractions.post writes abstractions to shared."""
    shared = {}
    node = IdentifyAbstractions()
    exec_res = [{"name": "A", "description": "d", "files": [0]}]
    action = node.post(shared, {}, exec_res)
    assert action == "default"
    assert shared["abstractions"] == exec_res


# --- AnalyzeRelationships ---


def test_analyze_relationships_exec_parses_yaml_and_converts_to_indices():
    """AnalyzeRelationships.exec parses YAML and converts from/to to indices (mock call_llm)."""
    prep_res = {
        "project_name": "p",
        "language": "english",
        "abstraction_list": "0 # Node\n1 # Flow",
        "context": "Identified Abstractions:\n- Node\n- Flow",
        "use_cache": True,
        "num_abstractions": 2,
    }
    yaml_response = """```yaml
summary: A pipeline framework.
relationships:
  - from_abstraction: "0 # Node"
    to_abstraction: "1 # Flow"
    label: executes
```"""
    with patch("nodes.call_llm", return_value=yaml_response):
        node = AnalyzeRelationships()
        result = node.exec(prep_res)
    assert result["summary"] == "A pipeline framework."
    assert len(result["details"]) == 1
    assert result["details"][0]["from"] == 0
    assert result["details"][0]["to"] == 1
    assert result["details"][0]["label"] == "executes"


def test_analyze_relationships_post_writes_relationships():
    """AnalyzeRelationships.post writes relationships to shared."""
    shared = {}
    node = AnalyzeRelationships()
    exec_res = {"summary": "s", "details": [{"from": 0, "to": 1, "label": "l"}]}
    action = node.post(shared, {}, exec_res)
    assert action == "default"
    assert shared["relationships"] == exec_res


# --- OrderChapters ---


def test_order_chapters_exec_parses_yaml_and_validates_all_indices_once():
    """OrderChapters.exec parses YAML and validates all abstraction indices present once (mock call_llm)."""
    prep_res = {
        "abstractions": [{"name": "A"}, {"name": "B"}],
        "project_name": "p",
        "language": "english",
        "abstraction_list": "0 # A\n1 # B",
        "relationships_text": "A -> B",
    }
    yaml_response = """
- "0 # A"
- "1 # B"
"""
    with patch("nodes.call_llm", return_value=yaml_response):
        node = OrderChapters()
        result = node.exec(prep_res)
    assert result == [0, 1]


def test_order_chapters_exec_raises_when_indices_incomplete():
    """OrderChapters.exec raises when not all abstraction indices appear exactly once."""
    prep_res = {
        "abstractions": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
        "project_name": "p",
        "language": "english",
        "abstraction_list": "0 # A\n1 # B\n2 # C",
        "relationships_text": "",
    }
    yaml_response = """
- "0 # A"
- "1 # B"
"""
    with patch("nodes.call_llm", return_value=yaml_response):
        node = OrderChapters()
        with pytest.raises(ValueError, match="each abstraction index exactly once"):
            node.exec(prep_res)


def test_order_chapters_post_writes_chapter_order():
    """OrderChapters.post writes chapter_order to shared."""
    shared = {}
    node = OrderChapters()
    exec_res = [1, 0, 2]
    action = node.post(shared, {}, exec_res)
    assert action == "default"
    assert shared["chapter_order"] == [1, 0, 2]


# --- WriteChapters (BatchNode) ---


def test_write_chapters_prep_returns_iterable_per_chapter_order():
    """WriteChapters.prep returns list of items (one per abstraction in chapter_order)."""
    shared = {
        "chapter_order": [0, 1],
        "abstractions": [{"name": "A", "description": "d1", "files": [0]}, {"name": "B", "description": "d2", "files": [1]}],
        "files": [("a.py", "x"), ("b.py", "y")],
        "project_name": "p",
        "language": "english",
    }
    node = WriteChapters()
    prep_res = node.prep(shared)
    assert len(prep_res) == 2
    assert prep_res[0]["abstraction_name"] == "A"
    assert prep_res[0]["chapter_number"] == 1
    assert prep_res[1]["abstraction_name"] == "B"
    assert "0 # a.py" in prep_res[0].get("file_content_map", {})


def test_write_chapters_exec_returns_chapter_content_mock_llm():
    """WriteChapters.exec(item) calls call_llm and returns chapter content (mock)."""
    node = WriteChapters()
    node.chapters_written_so_far = []
    item = {
        "chapter_number": 1,
        "abstraction_name": "Node",
        "abstraction_description": "A step.",
        "file_content_map": {"0 # a.py": "code"},
        "chapter_list_with_numbers": "1. Node",
        "language": "english",
        "project_name": "p",
    }
    with patch("nodes.call_llm", return_value="# Node\n\nThis chapter explains Node."):
        result = node.exec(item)
    assert "Node" in result
    assert len(node.chapters_written_so_far) == 1


def test_write_chapters_post_writes_chapters_to_shared():
    """WriteChapters.post assigns exec_res_list to shared['chapters']."""
    shared = {}
    node = WriteChapters()
    exec_res_list = ["# Ch1\ncontent1", "# Ch2\ncontent2"]
    action = node.post(shared, [], exec_res_list)
    assert action == "default"
    assert shared["chapters"] == exec_res_list


# --- CombineTutorial ---


def test_combine_tutorial_prep_builds_mermaid_and_index_content():
    """CombineTutorial.prep builds output_path, index_content, chapter_files."""
    shared = {
        "project_name": "myproj",
        "relationships": {"summary": "A pipeline.", "details": [{"from": 0, "to": 1, "label": "runs"}]},
        "chapter_order": [0, 1],
        "abstractions": [{"name": "Node"}, {"name": "Flow"}],
        "chapters": ["# Node\nx", "# Flow\ny"],
        "output_dir": "out",
    }
    node = CombineTutorial()
    prep_res = node.prep(shared)
    assert "output_path" in prep_res
    assert "myproj" in prep_res["output_path"]
    assert "flowchart TD" in prep_res["index_content"]
    assert "Node" in prep_res["index_content"]
    assert "Flow" in prep_res["index_content"]
    assert len(prep_res["chapter_files"]) == 2
    assert prep_res["chapter_files"][0]["filename"].endswith(".md")


def test_combine_tutorial_exec_creates_dir_and_writes_files(tmp_path):
    """CombineTutorial.exec creates output dir and writes index.md and chapter files."""
    prep_res = {
        "output_path": str(tmp_path / "tutorial"),
        "index_content": "# Proj\nSummary.",
        "chapter_files": [{"filename": "01_node.md", "content": "# Node\nx"}, {"filename": "02_flow.md", "content": "# Flow\ny"}],
        "repo_url": "",
    }
    node = CombineTutorial()
    out_path = node.exec(prep_res)
    assert out_path == str(tmp_path / "tutorial")
    assert (tmp_path / "tutorial" / "index.md").exists()
    assert (tmp_path / "tutorial" / "01_node.md").read_text() == "# Node\nx"
    assert (tmp_path / "tutorial" / "02_flow.md").read_text() == "# Flow\ny"


def test_combine_tutorial_post_writes_final_output_dir():
    """CombineTutorial.post sets shared['final_output_dir']."""
    shared = {}
    node = CombineTutorial()
    action = node.post(shared, {}, "/out/proj")
    assert action == "default"
    assert shared["final_output_dir"] == "/out/proj"
