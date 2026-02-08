# Task List: Codebase Knowledge Builder (MVP)

Generated from [docs/design.md](../docs/design.md) and [.cursor/plans/prd_codebase_knowledge_builder_2dfde023.plan.md](../.cursor/plans/prd_codebase_knowledge_builder_2dfde023.plan.md).

## Relevant Files

- `main.py` – CLI entrypoint, shared store initialization, flow run.
- `flow.py` – Flow definition and node connections (FetchRepo → … → CombineTutorial).
- `nodes.py` – Node classes: FetchRepo, IdentifyAbstractions, AnalyzeRelationships, OrderChapters, WriteChapters (BatchNode), CombineTutorial.
- `utils/crawl_github_files.py` – GitHub repo crawler; returns `files` dict and `stats`.
- `utils/crawl_local_files.py` – Local directory crawler; returns `files` dict.
- `utils/call_llm.py` – LLM wrapper (prompt → response); multi-provider via env (Gemini default, optional Cursor CLI).
- `utils/context_helpers.py` – Helpers `create_llm_context` and `get_content_for_indices` for formatting file/indices for LLM prompts.
- `utils/__init__.py` – Package init for utils.
- `requirements.txt` – Dependencies (pocketflow, requests, PyYAML, LLM client; optional GitPython for GitHub).
- `README.md` – Usage, CLI args, env vars, how to run.
- `docs/design.md` – Existing design (reference only).
- `tests/test_crawl_local.py` – Unit tests for `crawl_local_files`.
- `tests/test_crawl_github.py` – Unit tests for `crawl_github_files` (or skip if mocking GitHub is heavy).
- `tests/test_call_llm.py` – Unit tests for `call_llm` (e.g. mock API).
- `tests/test_nodes.py` – Unit tests for nodes (prep/post/exec contracts, shared store).
- `tests/test_flow.py` – Integration test: minimal flow run, shared store populated.

### Notes

- Unit tests can live alongside code or in `tests/`; use `pytest` to run (e.g. `pytest` or `pytest tests/`).
- Design doc specifies shared store keys and types; keep `main.py` or a small `shared_schema` / defaults in one place.
- For YAML from LLM: parse with `yaml.safe_load`, validate indices against `len(files)` / `len(abstractions)` and retry or fail clearly.
- `call_llm` supports multiple backends via `LLM_PROVIDER`: `gemini` (default, uses `GEMINI_API_KEY`) or `cursor` (Cursor CLI via subprocess; uses `CURSOR_MODEL`, `CURSOR_TIMEOUT`, `CURSOR_API_KEY` for headless).

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, check it off in this markdown file by changing `- [ ]` to `- [x]`. Update after each sub-task, not only after an entire parent task.

## Tasks

- [x] 0.0 Create feature branch
  - [x] 0.1 Create and checkout a new branch for this feature (e.g., `git checkout -b feature/codebase-knowledge-builder`)
- [x] 1.0 Foundation — shared store, utilities, FetchRepo, CLI skeleton
  - [x] 1.1 Define shared store schema and defaults per design (e.g. in main or a small shared module); document keys used by nodes.
  - [x] 1.2 Implement `utils/crawl_local_files.py` (directory, max_file_size, use_relative_paths, include/exclude patterns → dict `files`).
  - [x] 1.3 Implement `utils/crawl_github_files.py` (repo_url, token, max_file_size, etc. → dict `files` and `stats`).
  - [x] 1.4 Implement `utils/call_llm.py` (prompt, optional use_cache → response str); read API key from environment.
  - [x] 1.4a Add Cursor CLI as optional backend: when `LLM_PROVIDER=cursor`, invoke `agent` via subprocess (prompt via stdin or temp file), `--output-format text`; respect `CURSOR_MODEL`, `CURSOR_TIMEOUT`, `CURSOR_API_KEY`; document env vars in README.
  - [x] 1.5 Implement FetchRepo node in `nodes.py` (prep/exec/post per design; call crawl_github or crawl_local; write `files` list of (path, content) and `project_name` to shared).
  - [x] 1.6 Create minimal flow in `flow.py` (FetchRepo only) and run it from `main.py`.
  - [x] 1.7 Add CLI skeleton: parse `--repo-url`, `--local-dir`, optional `--project-name`, `--output-dir`, `--language`; populate shared and run flow; clear help and exit codes.
- [x] 2.0 Analysis — IdentifyAbstractions, AnalyzeRelationships, OrderChapters nodes and flow wiring
  - [x] 2.1 Add helpers `create_llm_context` and `get_content_for_indices` in `utils/context_helpers.py` (format file list with indices and get content for given indices for LLM prompts).
  - [x] 2.2 Implement IdentifyAbstractions node (prep: files, project_name, language; exec: call_llm, parse YAML, validate indices; post: write `abstractions`).
  - [x] 2.3 Implement AnalyzeRelationships node (prep: abstractions, files, language; exec: call_llm, parse YAML, validate from/to indices; post: write `relationships`).
  - [x] 2.4 Implement OrderChapters node (prep: abstractions, relationships, language; exec: call_llm, parse YAML, validate order; post: write `chapter_order`).
  - [x] 2.5 Wire IdentifyAbstractions → AnalyzeRelationships → OrderChapters into flow after FetchRepo.
- [x] 3.0 Content — WriteChapters (BatchNode), CombineTutorial, Mermaid, index.md and chapter files
  - [x] 3.1 Implement WriteChapters as BatchNode (prep: return iterable per `chapter_order` with chapter number, abstraction details, file content map, chapter list; exec(item): call_llm for one chapter, accumulate in `chapters_written_so_far`; post: set `shared["chapters"]` from exec_res_list).
  - [x] 3.2 Implement CombineTutorial node (prep: build Mermaid flowchart string, index.md content, chapter file list with attribution footer; exec: create output dir, write index.md and each chapter .md; post: set `shared["final_output_dir"]`).
  - [x] 3.3 Wire WriteChapters and CombineTutorial into flow (OrderChapters >> WriteChapters >> CombineTutorial).
  - [x] 3.4 Verify end-to-end: run pipeline on a small repo or local dir; assert output dir contains index.md and N chapter files with valid Mermaid.
- [x] 4.0 Polish — language option end-to-end, error handling and logging, docs and README, basic quality checks
  - [x] 4.1 Add language handling end-to-end: ensure IdentifyAbstractions, AnalyzeRelationships, OrderChapters, and WriteChapters include `language` in prompts and produce translated names/descriptions/summary/labels/chapters when language ≠ English.
  - [x] 4.2 Add error handling and logging: structured logging, exit code 0 on success and non-zero on failure, log key steps and errors.
  - [x] 4.3 Update README and docs: CLI usage (args, env vars), requirements, how to run, example; reference design.md.
  - [x] 4.4 Manual quality checks: run on one public GitHub repo and one local directory; verify summary and chapter order; optionally run with one non-English language and verify coherent output. (Documented in README under "Manual quality checks (optional)".)
