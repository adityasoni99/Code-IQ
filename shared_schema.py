"""
Shared store schema and defaults for the Code-IQ pipeline.

Keys used by nodes (see docs/design.md § Node Design / Shared Store):

Inputs (set by CLI/main):
- repo_url: Optional[str] — GitHub repository URL.
- local_dir: Optional[str] — Local directory path (alternative to repo_url).
- project_name: Optional[str] — Derived from repo_url or local_dir if not provided.
- github_token: Optional[str] — For GitHub API (argument or env).
- output_dir: str — Base directory for output (default "output").
- include_patterns: set — File glob patterns to include.
- exclude_patterns: set — File glob patterns to exclude.
- max_file_size: int — Max bytes per file (default 100000).
- language: str — Tutorial language (default "english").

Intermediate/Output (written by nodes):
- files: list — Output of FetchRepo; list of (file_path: str, file_content: str).
- abstractions: list — Output of IdentifyAbstractions; list of {"name", "description", "files": [int]}.
- relationships: dict — Output of AnalyzeRelationships; {"summary": str, "details": [{"from", "to", "label"}]}.
- chapter_order: list — Output of OrderChapters; indices into abstractions.
- chapters: list — Output of WriteChapters; list of Markdown chapter strings.
- final_output_dir: Optional[str] — Output of CombineTutorial; path to generated tutorial dir.
"""


def default_shared_store() -> dict:
    """Return a new shared store dict with default keys and values."""
    return {
        "repo_url": None,
        "local_dir": None,
        "project_name": None,
        "github_token": None,
        "output_dir": "output",
        "include_patterns": set(),
        "exclude_patterns": set(),
        "max_file_size": 100_000,
        "language": "english",
        "files": [],
        "all_files": [],
        "abstractions": [],
        "file_summary": "",
        "relationships": {
            "summary": None,
            "details": [],
        },
        "chapter_order": [],
        "chapters": [],
        "final_output_dir": None,
    }
