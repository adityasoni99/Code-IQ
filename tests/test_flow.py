"""Integration tests: minimal flow run, shared store populated."""

from unittest.mock import patch

from shared_schema import default_shared_store
from flow import create_analysis_flow, create_fetch_flow, create_full_flow


def test_minimal_flow_runs_and_populates_shared_with_local_dir():
    """Running the flow with local_dir and mocked crawl_local populates shared['files'] and shared['project_name']."""
    shared = default_shared_store()
    shared["local_dir"] = "/tmp/sample"
    shared["repo_url"] = None
    with patch("nodes.crawl_local_files") as mock_crawl:
        mock_crawl.return_value = {"files": {"a.py": "x", "b.py": "y"}}
        flow = create_fetch_flow()
        flow.run(shared)
    assert len(shared["files"]) == 2
    files_dict = dict(shared["files"])
    assert files_dict["a.py"] == "x"
    assert files_dict["b.py"] == "y"
    assert shared["project_name"] == "sample"


def test_minimal_flow_runs_and_populates_shared_with_repo_url():
    """Running the flow with repo_url and mocked crawl_github populates shared['files'] and shared['project_name']."""
    shared = default_shared_store()
    shared["repo_url"] = "https://github.com/owner/repo"
    shared["local_dir"] = None
    with patch("nodes.crawl_github_files") as mock_crawl:
        mock_crawl.return_value = {"files": {"readme.md": "hi"}, "stats": {}}
        flow = create_fetch_flow()
        flow.run(shared)
    assert len(shared["files"]) == 1
    assert dict(shared["files"])["readme.md"] == "hi"
    assert shared["project_name"] == "repo"


def test_create_fetch_flow_returns_flow():
    """create_fetch_flow returns a Flow instance."""
    flow = create_fetch_flow()
    assert flow is not None
    from pocketflow import Flow
    assert isinstance(flow, Flow)


# --- Analysis flow (FetchRepo -> IdentifyAbstractions -> AnalyzeRelationships -> OrderChapters) ---


def test_analysis_flow_populates_abstractions_relationships_chapter_order():
    """Running analysis flow with mocked crawl and call_llm populates abstractions, relationships, chapter_order."""
    shared = default_shared_store()
    shared["local_dir"] = "/tmp/sample"
    shared["repo_url"] = None
    shared["files"] = [("a.py", "x"), ("b.py", "y")]

    def fake_call_llm(prompt: str, use_cache: bool = True) -> str:
        # SummarizeFiles - select representative files
        if "representative file paths" in prompt or "summarize the area" in prompt:
            return """```yaml
summary: Test files
files: [a.py, b.py]
```"""
        if "most representative" in prompt and "candidate file list" in prompt:
            return "- a.py\n- b.py"
        # OrderChapters has unique text
        if "best order to explain" in prompt or "tutorial for" in prompt:
            return """```yaml
- "0 # Node"
- "1 # Flow"
```"""
        # AnalyzeRelationships has from_abstraction / to_abstraction
        if "from_abstraction" in prompt or "to_abstraction" in prompt or "EVERY abstraction" in prompt:
            return """```yaml
summary: A pipeline.
relationships:
  - from_abstraction: "0 # Node"
    to_abstraction: "1 # Flow"
    label: runs
```"""
        # IdentifyAbstractions: file list + "Identify" abstractions
        return """```yaml
- name: Node
  description: A step.
  file_indices: [0]
- name: Flow
  description: Orchestrator.
  file_indices: [1]
```"""

    with patch("nodes.crawl_local_files") as mock_crawl:
        mock_crawl.return_value = {"files": {"a.py": "x", "b.py": "y"}}
        with patch("nodes.call_llm", side_effect=fake_call_llm):
            flow = create_analysis_flow()
            flow.run(shared)

    assert len(shared["files"]) == 2
    assert shared["project_name"] == "sample"
    assert len(shared["abstractions"]) == 2
    assert shared["abstractions"][0]["name"] == "Node"
    assert shared["relationships"]["summary"] == "A pipeline."
    assert len(shared["relationships"]["details"]) == 1
    assert shared["chapter_order"] == [0, 1]


def test_full_flow_produces_output_dir_with_index_and_chapters(tmp_path):
    """Full flow (FetchRepo -> ... -> CombineTutorial) produces output dir with index.md and chapter files (all mocked)."""
    from pathlib import Path
    shared = default_shared_store()
    shared["local_dir"] = "/tmp/sample"
    shared["repo_url"] = None
    shared["output_dir"] = str(tmp_path)
    shared["files"] = [("a.py", "x"), ("b.py", "y")]

    def fake_call_llm(prompt: str, use_cache: bool = True) -> str:
        if "best order to explain" in prompt or "tutorial for" in prompt:
            return '```yaml\n- "0 # Node"\n- "1 # Flow"\n```'
        if "from_abstraction" in prompt or "to_abstraction" in prompt or "EVERY abstraction" in prompt:
            return """```yaml
summary: A pipeline.
relationships:
  - from_abstraction: "0 # Node"
    to_abstraction: "1 # Flow"
    label: runs
```"""
        if "beginner-friendly tutorial chapter" in prompt or ("Chapter" in prompt and "Relevant Code" in prompt):
            return "# Chapter\n\nThis chapter explains the concept."
        return """```yaml
- name: Node
  description: A step.
  file_indices: [0]
- name: Flow
  description: Orchestrator.
  file_indices: [1]
```"""

    with patch("nodes.crawl_local_files") as mock_crawl:
        mock_crawl.return_value = {"files": {"a.py": "x", "b.py": "y"}}
        with patch("nodes.call_llm", side_effect=fake_call_llm):
            flow = create_full_flow()
            flow.run(shared)

    assert shared.get("final_output_dir")
    out_dir = Path(shared["final_output_dir"])
    assert out_dir.exists()
    index_path = out_dir / "index.md"
    assert index_path.exists(), f"expected index.md in {out_dir}, got {list(out_dir.iterdir())}"
    content = index_path.read_text()
    assert "flowchart" in content or "Relationships" in content
    assert "```mermaid" in content, "index.md should contain a Mermaid diagram block"
    assert "Chapters" in content, "index.md should list Chapters section"
    chapter_mds = sorted(f for f in out_dir.glob("*.md") if f.name != "index.md")
    assert len(chapter_mds) >= 2, f"expected at least 2 chapter files, got {chapter_mds}"
    assert chapter_mds[0].name.startswith("01_"), "first chapter should be 01_*.md"
    assert chapter_mds[1].name.startswith("02_"), "second chapter should be 02_*.md"
