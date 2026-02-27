"""
PocketFlow nodes for the Code-IQ pipeline.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pocketflow import BatchNode, Node

from utils.context_helpers import create_llm_context, get_content_for_indices
from utils.dir_helpers import (
    count_files_under,
    get_direct_subdirs,
    has_direct_subdirs,
    is_completed,
)

logger = logging.getLogger("Code_IQ")
from utils.crawl_github_files import crawl_github_files
from utils.crawl_local_files import crawl_local_files
from utils.call_llm import call_llm


def _extract_yaml_block(text: str) -> str:
    """Extract YAML from markdown code block if present, else return text."""
    text = text.strip()
    for pattern in (r"```yaml\s*\n(.*?)\n```", r"```\s*\n(.*?)\n```"):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return text


def _extract_yaml_list_block(text: str) -> str:
    """Extract the first YAML list block from text, if present."""
    lines = text.strip().splitlines()
    if not lines:
        return text
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("- "):
            start = i
            break
    if start is None:
        return text
    block_lines = []
    in_block = False
    for line in lines[start:]:
        if line.lstrip().startswith("- "):
            in_block = True
            block_lines.append(line)
            continue
        if not in_block:
            continue
        if line.strip() == "" or line.startswith(" ") or line.startswith("\t"):
            block_lines.append(line)
            continue
        # Stop on a new top-level line that is not part of the list.
        break
    return "\n".join(block_lines).strip() or text


def _try_parse_list(text: str) -> list | None:
    """Try parsing YAML or JSON list from text; return list or None."""
    if not text:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None
    if isinstance(data, dict):
        data = data.get("abstractions") or data.get("items") or data.get("list") or data
    if isinstance(data, list):
        return data
    # Try JSON list directly if YAML failed or returned non-list
    try:
        data = json.loads(text)
    except Exception:
        return None
    if isinstance(data, dict):
        data = data.get("abstractions") or data.get("items") or data.get("list") or data
    return data if isinstance(data, list) else None


def _try_parse_dict(text: str) -> dict | None:
    """Try parsing YAML or JSON dict from text; return dict or None."""
    if not text:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None
    if isinstance(data, dict):
        return data
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _parse_index_from_ref(ref: str | int) -> int:
    """Convert '0 # path' or '0 # Name' or 0 to int index."""
    if isinstance(ref, int):
        return ref
    s = str(ref).strip()
    first = s.split("#")[0].strip() or s.split()[0] if s.split() else ""
    return int(first)


def _derive_project_name(
    repo_url: Any, local_dir: Any, existing: Any
) -> str:
    """Derive project name from repo_url or local_dir if not already set."""
    if existing and str(existing).strip():
        return str(existing).strip()
    if repo_url and str(repo_url).strip():
        # e.g. https://github.com/owner/repo -> repo
        url = str(repo_url).strip().rstrip("/")
        name = url.split("/")[-1].removesuffix(".git") if "/" in url else url
        return name or "project"
    if local_dir and str(local_dir).strip():
        return os.path.basename(os.path.abspath(str(local_dir).strip())) or "project"
    return "project"


def _collect_leaf_folders(
    parent: Path,
    children_output_base: Path,
    file_threshold: int,
    skip_hidden: bool,
    resume: bool,
) -> list[dict[str, str]]:
    """
    Recursively collect leaf folder entries (local_dir, output_dir, project_name).
    Emits leaves first, then the parent itself as the last entry (current-folder-last).
    Skips completed folders when resume is True.
    """
    result: list[dict[str, str]] = []
    subdirs = get_direct_subdirs(parent, skip_hidden)

    for subdir in subdirs:
        local_dir = subdir.resolve()
        nfiles = count_files_under(local_dir)
        has_subdirs_flag = has_direct_subdirs(local_dir, skip_hidden)

        if nfiles > file_threshold and has_subdirs_flag:
            next_output = children_output_base / subdir.name
            result.extend(
                _collect_leaf_folders(
                    local_dir,
                    next_output,
                    file_threshold,
                    skip_hidden,
                    resume,
                )
            )
        else:
            if resume and is_completed(children_output_base, subdir.name):
                continue
            result.append({
                "local_dir": str(local_dir),
                "output_dir": str(children_output_base),
                "project_name": subdir.name,
            })

    # Parent as current folder (last entry)
    if resume and is_completed(children_output_base.parent, parent.name):
        pass  # skip appending parent
    else:
        result.append({
            "local_dir": str(parent.resolve()),
            "output_dir": str(children_output_base.parent),
            "project_name": parent.name,
        })
    return result


class DiscoverLeafFolders(Node):
    """
    Discover leaf folders for recursive BatchFlow processing.

    prep: Read parent_dirs, file_threshold, skip_hidden, resume, output_dir from shared.
    exec: Recursive walk with threshold and checkpoint; emit leaves then parent-last per parent.
    post: Write leaf_folders list to shared, return "default".
    """

    def prep(self, shared: dict) -> dict:
        parent_dirs = shared.get("parent_dirs") or []
        file_threshold = int(shared.get("file_threshold") or 100)
        skip_hidden = shared.get("skip_hidden", True)
        resume = shared.get("resume", True)
        output_dir = (shared.get("output_dir") or "output").strip()
        return {
            "parent_dirs": parent_dirs,
            "file_threshold": file_threshold,
            "skip_hidden": skip_hidden,
            "resume": resume,
            "output_dir": output_dir,
        }

    def exec(self, prep_res: dict) -> list[dict[str, str]]:
        parent_dirs = prep_res.get("parent_dirs") or []
        file_threshold = prep_res.get("file_threshold", 100)
        skip_hidden = prep_res.get("skip_hidden", True)
        resume = prep_res.get("resume", True)
        output_dir = Path(prep_res.get("output_dir", "output").strip())
        result: list[dict[str, str]] = []
        for parent_raw in parent_dirs:
            parent = Path(parent_raw).resolve()
            if not parent.is_dir():
                logger.warning("DiscoverLeafFolders: skipping non-directory %s", parent)
                continue
            children_output_base = output_dir / parent.name
            result.extend(
                _collect_leaf_folders(
                    parent,
                    children_output_base,
                    file_threshold,
                    skip_hidden,
                    resume,
                )
            )
        return result

    def post(
        self, shared: dict, prep_res: dict, exec_res: list[dict[str, str]]
    ) -> str:
        shared["leaf_folders"] = exec_res
        shared["total_folders"] = len(exec_res)
        return "default"


class UpdateJobProgress(Node):
    """
    Updates job progress in the job store after each folder (recursive batch).
    Reads job_id, total_folders, _progress_completed from shared; increments and writes progress.
    """

    def prep(self, shared: dict) -> dict:
        return {
            "job_id": shared.get("job_id"),
            "total_folders": shared.get("total_folders", 0),
            "project_name": shared.get("project_name", ""),
        }

    def exec(self, prep_res: dict) -> None:
        return None

    def post(self, shared: dict, prep_res: dict, exec_res: None) -> str:
        job_id = prep_res.get("job_id")
        if not job_id:
            return "default"
        try:
            from api import job_store

            completed = shared.get("_progress_completed", 0) + 1
            shared["_progress_completed"] = completed
            total = prep_res.get("total_folders", 0)
            current_folder = prep_res.get("project_name", "") or ""
            job_store.update_progress(job_id, completed, total, current_folder)
        except Exception as e:
            logger.warning("UpdateJobProgress failed: %s", e)
        return "default"


class FetchRepo(Node):
    """
    Fetch repository code from GitHub or local directory.

    prep: Read repo_url, local_dir, project_name, github_token, include/exclude patterns, max_file_size from shared.
    exec: Call crawl_github_files or crawl_local_files; convert files dict to list of (path, content) tuples.
    post: Write files and project_name to shared.
    """

    def prep(self, shared: dict) -> dict:
        repo_url = self.params.get("repo_url", shared.get("repo_url"))
        local_dir = self.params.get("local_dir", shared.get("local_dir"))
        output_dir = self.params.get("output_dir", shared.get("output_dir", "output"))
        project_name = _derive_project_name(
            repo_url, local_dir, self.params.get("project_name", shared.get("project_name"))
        )
        return {
            "repo_url": repo_url,
            "local_dir": local_dir,
            "project_name": project_name,
            "github_token": shared.get("github_token"),
            "output_dir": output_dir,
            "include_patterns": shared.get("include_patterns") or set(),
            "exclude_patterns": shared.get("exclude_patterns") or set(),
            "max_file_size": shared.get("max_file_size", 100_000),
            "use_relative_paths": True,
        }

    def exec(self, prep_res: dict) -> tuple[list[tuple[str, str]], str]:
        repo_url = prep_res.get("repo_url")
        local_dir = prep_res.get("local_dir")
        project_name = prep_res.get("project_name", "project")
        include = prep_res.get("include_patterns") or set()
        exclude = prep_res.get("exclude_patterns") or set()
        max_size = prep_res.get("max_file_size", 100_000)
        use_relative = prep_res.get("use_relative_paths", True)

        if repo_url and str(repo_url).strip():
            print(f"Crawling repository: {repo_url}...")
            result = crawl_github_files(
                repo_url=str(repo_url).strip(),
                token=prep_res.get("github_token"),
                max_file_size=max_size,
                use_relative_paths=use_relative,
                include_patterns=include or None,
                exclude_patterns=exclude or None,
            )
            files_dict = result.get("files") or {}
        else:
            if not local_dir or not str(local_dir).strip():
                raise ValueError("Either repo_url or local_dir must be set in shared store")
            print(f"Crawling local directory: {local_dir}...")
            result = crawl_local_files(
                directory=str(local_dir).strip(),
                max_file_size=max_size,
                use_relative_paths=use_relative,
                include_patterns=include or None,
                exclude_patterns=exclude or None,
            )
            files_dict = result.get("files") or {}

        files_list = list(files_dict.items())
        if len(files_list) == 0:
            raise (ValueError("Failed to fetch files"))
        return (files_list, project_name)

    def post(
        self, shared: dict, prep_res: dict, exec_res: tuple[list[tuple[str, str]], str]
    ) -> str:
        files_list, project_name = exec_res
        shared["files"] = files_list
        shared["all_files"] = files_list
        shared["project_name"] = project_name
        logger.info("FetchRepo: files=%s, project_name=%s", len(files_list), project_name)
        return "default"


class SummarizeFiles(Node):
    """
    Summarize file list and select representative files before abstractions.

    prep: Read files and project_name.
    exec: Chunk paths, summarize each chunk (summary + files list), then merge and select final paths.
    post: Replace shared["files"] with filtered list; store summary in shared["file_summary"].
    """

    def prep(self, shared: dict) -> dict:
        files = shared.get("files") or []
        project_name = shared.get("project_name") or "project"
        return {"files": files, "project_name": project_name}

    def exec(self, prep_res: dict) -> dict:
        files = prep_res.get("files") or []
        project_name = prep_res.get("project_name") or "project"
        paths = [path for path, _ in files]
        if not paths:
            return {"paths": [], "summary": ""}

        chunk_size = int(os.environ.get("LLM_FILE_SUMMARY_CHUNK_SIZE", "1000") or "1000")
        chunk_size = max(50, min(chunk_size, 5000))
        max_files = int(os.environ.get("LLM_FILE_SUMMARY_MAX_FILES", "400") or "400")
        max_files = max(50, min(max_files, 2000))

        chunk_summaries: list[str] = []
        chunk_files: list[str] = []
        for i in range(0, len(paths), chunk_size):
            chunk = paths[i : i + chunk_size]
            chunk_list = "\n".join(f"- {p}" for p in chunk)
            prompt = (
                f"Project: {project_name}\n\n"
                "Given this file path list, summarize the area in 3-5 bullets and select 20-40 "
                "representative file paths from this chunk. Output YAML with keys:\n"
                "summary: <string>\n"
                "files: [path1, path2, ...]\n"
                "No prose outside YAML.\n\n"
                f"Files:\n{chunk_list}"
            )
            response = call_llm(prompt)
            raw = _extract_yaml_block(response)
            data = _try_parse_dict(raw)
            if not isinstance(data, dict):
                data = _try_parse_dict(_extract_yaml_list_block(response))
            summary = ""
            files_list = []
            if isinstance(data, dict):
                summary = str(data.get("summary") or "").strip()
                files_list = data.get("files") or []
            if not isinstance(files_list, list):
                files_list = []
            selected = [str(p).strip() for p in files_list if str(p).strip()]
            if not selected:
                selected = chunk[: min(30, len(chunk))]
            if summary:
                chunk_summaries.append(summary)
            chunk_files.extend(selected)

        merged_files = _dedupe_keep_order(chunk_files)
        merged_summary = "\n".join(f"- {s}" for s in chunk_summaries if s)

        merge_prompt = (
            f"Project: {project_name}\n\n"
            "You are given chunk summaries and a candidate file list. Select the most representative "
            f"files (target {max_files}) that best explain the codebase. Output a YAML list of file paths only. "
            "No prose, no code fences.\n\n"
            f"Summaries:\n{merged_summary}\n\n"
            "Candidate files:\n"
            + "\n".join(f"- {p}" for p in merged_files)
        )
        merge_response = call_llm(merge_prompt)
        merge_raw = _extract_yaml_block(merge_response)
        final_paths = _try_parse_list(merge_raw)
        if not isinstance(final_paths, list):
            merge_list = _extract_yaml_list_block(merge_response)
            final_paths = _try_parse_list(merge_list)
        if not isinstance(final_paths, list) or not final_paths:
            final_paths = merged_files[:max_files]
        final_paths = _dedupe_keep_order([str(p).strip() for p in final_paths if str(p).strip()])
        if "README.md" in paths and "README.md" not in final_paths:
            final_paths.insert(0, "README.md")

        return {"paths": final_paths[:max_files], "summary": merged_summary}

    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        files = prep_res.get("files") or []
        path_set = set(exec_res.get("paths") or [])
        if not path_set:
            return "default"
        filtered = [(path, content) for path, content in files if path in path_set]
        shared["files"] = filtered
        shared["file_summary"] = exec_res.get("summary") or ""
        logger.info("SummarizeFiles: selected_files=%s (from %s)", len(filtered), len(files))
        return "default"


class IdentifyAbstractions(Node):
    """
    Identify core abstractions from files using LLM; output name, description, file indices.

    prep: Read files, project_name, language, use_cache, max_abstraction_num; build index # path context.
    exec: Prompt call_llm for YAML list of {name, description, files: [indices]}; parse and validate indices.
    post: Write abstractions to shared.
    """

    def prep(self, shared: dict) -> dict:
        files = shared.get("files") or []
        project_name = shared.get("project_name") or "project"
        language = (shared.get("language") or "english").strip().lower()
        use_cache = shared.get("use_cache", True)
        max_abstraction_num = shared.get("max_abstraction_num", 10)

        file_context, file_info = create_llm_context(files)
        # Build file listing for prompt
        file_listing = "\n".join(f"- {i} # {path}" for i, path in file_info)
        return {
            "n_files": len(files),
            "project_name": project_name,
            "language": language,
            "file_context": file_context,
            "file_listing": file_listing,
            "use_cache": use_cache,
            "max_abstraction_num": max_abstraction_num,
        }

    def exec(self, prep_res: dict) -> list[dict]:
        n_files = prep_res.get("n_files") or 0
        project_name = prep_res.get("project_name") or "project"
        language = prep_res.get("language") or "english"
        file_context = prep_res.get("file_context") or ""
        file_listing = prep_res.get("file_listing") or ""
        use_cache = prep_res.get("use_cache", True)
        max_abstraction_num = prep_res.get("max_abstraction_num", 10)
        logger.info("Identifying abstractions using LLM...")

        # Add language instruction and hints only if not English
        language_instruction = ""
        name_lang_hint = ""
        desc_lang_hint = ""
        if language != "english":
            lang_cap = language.capitalize()
            language_instruction = f"IMPORTANT: Generate the `name` and `description` for each abstraction in **{lang_cap}** language. Do NOT use English for these fields.\n\n"
            name_lang_hint = f" (value in {lang_cap})"
            desc_lang_hint = f" (value in {lang_cap})"

        prompt = f"""For the project `{project_name}`:

Codebase Context:
{file_context}

{language_instruction}Analyze the codebase context.
Identify the top 5-{max_abstraction_num} core most important abstractions to help those new to the codebase.

For each abstraction, provide:
1. A concise `name`{name_lang_hint}.
2. A beginner-friendly `description` explaining what it is with a simple analogy, in around 100 words{desc_lang_hint}.
3. A list of relevant `file_indices` (integers) using the format `idx # path/comment`.

List of file indices and paths present in the context:
{file_listing}

Format the output as a YAML list of dictionaries:

```yaml
- name: |
    Query Processing{name_lang_hint}
  description: |
    Explains what the abstraction does.
    It's like a central dispatcher routing requests.{desc_lang_hint}
  file_indices:
    - 0 # path/to/file1.py
    - 3 # path/to/related.py
- name: |
    Query Optimization{name_lang_hint}
  description: |
    Another core concept, similar to a blueprint for objects.{desc_lang_hint}
  file_indices:
    - 5 # path/to/another.js
# ... up to {max_abstraction_num} abstractions
```"""
        # Use cache only if enabled and not retrying
        cache_flag = use_cache and getattr(self, "cur_retry", 0) == 0
        response = call_llm(prompt, use_cache=cache_flag)
        raw = _extract_yaml_block(response)
        data = _try_parse_list(raw)
        if not isinstance(data, list):
            raw_list = _extract_yaml_list_block(response)
            data = _try_parse_list(raw_list)
        if not isinstance(data, list):
            # Ask the model to reformat its own response into a strict YAML list.
            reform_prompt = (
                "Reformat the following content into a YAML list only. "
                "Each item must have keys: name, description, file_indices (list of ints). "
                "No prose, no code fences.\n\n"
                f"Content:\n{response}"
            )
            reform_response = call_llm(reform_prompt, use_cache=cache_flag)
            reform_raw = _extract_yaml_block(reform_response)
            data = _try_parse_list(reform_raw)
            if not isinstance(data, list):
                raw_list = _extract_yaml_list_block(reform_response)
                data = _try_parse_list(raw_list)
        if not isinstance(data, list):
            raise ValueError("LLM did not return a YAML list for abstractions")

        abstractions: list[dict] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("Name") or ""
            desc = item.get("description") or item.get("Description") or ""
            # Handle both file_indices (new format) and files (old format)
            files_raw = item.get("file_indices") or item.get("files") or item.get("Files") or []
            if not isinstance(files_raw, list):
                files_raw = [files_raw]
            indices = []
            for ref in files_raw:
                try:
                    idx = _parse_index_from_ref(ref)
                    if 0 <= idx < n_files:
                        indices.append(idx)
                except (ValueError, TypeError):
                    pass
            item["files"] = sorted(list(set(indices)))
            abstractions.append({"name": str(name).strip(), "description": str(desc).strip(), "files": item["files"]})
        logger.info("Identified %s abstractions: %s", len(abstractions), [a["name"] for a in abstractions])
        return abstractions

    def post(self, shared: dict, prep_res: dict, exec_res: list[dict]) -> str:
        shared["abstractions"] = exec_res # List of {"name": str, "description": str, "files": [int]}
        return "default"


class AnalyzeRelationships(Node):
    """
    Generate project summary and relationship details (from, to, label) using indices.

    prep: Read abstractions, files, project_name, language, use_cache; build context with get_content_for_indices.
    exec: Prompt call_llm for YAML {summary, details: [{from_abstraction, to_abstraction, label}]}; parse and validate.
    post: Write relationships to shared.
    """

    def prep(self, shared: dict) -> dict:
        abstractions = shared.get("abstractions") or []
        files = shared.get("files") or []
        project_name = shared.get("project_name") or "project"
        language = (shared.get("language") or "english").strip().lower()
        use_cache = shared.get("use_cache", True)
        
        # Build context with abstraction names, indices, descriptions, and relevant file snippets
        context_lines = ["Identified Abstractions:"]
        all_file_indices = set()
        abstraction_info_for_prompt = []
        for i, abstr in enumerate(abstractions):
            file_indices_str = ", ".join(map(str, abstr.get("files") or []))
            info_line = f"- Index {i}: {abstr.get('name', '')} (Relevant file indices: [{file_indices_str}])\n  Description: {abstr.get('description', '')}"
            context_lines.append(info_line)
            abstraction_info_for_prompt.append(f"{i} # {abstr.get('name', '')}")
            all_file_indices.update(abstr.get("files") or [])
        
        context_lines.append("\nRelevant File Snippets (Referenced by Index and Path):")
        relevant_files_content_map = get_content_for_indices(files, sorted(list(all_file_indices))) if files else {}
        content_snippets = "\\n\\n".join(
            f"--- File {key} ---\\n{content}"
            for key, content in relevant_files_content_map.items()
        )
        context_lines.append(content_snippets)
        
        return {
            "abstractions": abstractions,
            "files": files,
            "project_name": project_name,
            "language": language,
            "use_cache": use_cache,
            "abstraction_list": "\n".join(abstraction_info_for_prompt),
            "context": "\n".join(context_lines),
            "num_abstractions": len(abstractions),
        }

    def exec(self, prep_res: dict) -> dict:
        project_name = prep_res.get("project_name") or "project"
        language = prep_res.get("language") or "english"
        abs_list = prep_res.get("abstraction_list") or ""
        context = prep_res.get("context") or ""
        use_cache = prep_res.get("use_cache", True)
        n_abs = prep_res.get("num_abstractions", 0)

        logger.info("Analyzing relationships using LLM...")

        # Add language instruction and hints only if not English
        language_instruction = ""
        lang_hint = ""
        list_lang_note = ""
        if language.lower() != "english":
            lang_cap = language.capitalize()
            language_instruction = f"IMPORTANT: Generate the `summary` and relationship `label` fields in **{lang_cap}** language. Do NOT use English for these fields.\n\n"
            lang_hint = f" (in {lang_cap})"
            list_lang_note = f" (Names might be in {lang_cap})"

        prompt = f"""Based on the following abstractions and relevant code snippets from the project `{project_name}`:

List of Abstraction Indices and Names{list_lang_note}:
{abs_list}

Context (Abstractions, Descriptions, Code):
{context}

{language_instruction}Please provide:
1. A high-level `summary` of the project's main purpose and functionality in a few beginner-friendly sentences{lang_hint}. Use markdown formatting with **bold** and *italic* text to highlight important concepts.
2. A list (`relationships`) describing the key interactions between these abstractions. For each relationship, specify:
   - `from_abstraction`: Index of the source abstraction (e.g., `0 # AbstractionName1`)
   - `to_abstraction`: Index of the target abstraction (e.g., `1 # AbstractionName2`)
   - `label`: A brief label for the interaction **in just a few words**{lang_hint} (e.g., "Manages", "Inherits", "Uses").
   Ideally the relationship should be backed by one abstraction calling or passing parameters to another.
   Simplify the relationship and exclude those non-important ones.

IMPORTANT: Make sure EVERY abstraction is involved in at least ONE relationship (either as source or target). Each abstraction index must appear at least once across all relationships.

Format the output as YAML:

```yaml
summary: |
  A brief, simple explanation of the project{lang_hint}.
  Can span multiple lines with **bold** and *italic* for emphasis.
relationships:
  - from_abstraction: 0 # AbstractionName1
    to_abstraction: 1 # AbstractionName2
    label: "Manages"{lang_hint}
  - from_abstraction: 2 # AbstractionName3
    to_abstraction: 0 # AbstractionName1
    label: "Provides config"{lang_hint}
  # ... other relationships
```

Now, provide the YAML output:
"""
        # Use cache only if enabled and not retrying
        cache_flag = use_cache and getattr(self, "cur_retry", 0) == 0
        response = call_llm(prompt, use_cache=cache_flag)
        raw = _extract_yaml_block(response)
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM did not return a YAML dict for relationships")

        summary = data.get("summary") or data.get("Summary") or ""
        details_raw = data.get("details") or data.get("relationships") or data.get("Details") or []
        if not isinstance(details_raw, list):
            logger.warning("LLM returned non-list for relationships details; got: %s", type(details_raw))
            details_raw = []

        details: list[dict] = []
        for item in details_raw:
            if not isinstance(item, dict):
                logger.warning("Skipping invalid relationship item (not a dict): %s", item)
                continue
            from_ref = item.get("from_abstraction")
            if from_ref is None:
                from_ref = item.get("from")
            if from_ref is None:
                from_ref = ""
            to_ref = item.get("to_abstraction")
            if to_ref is None:
                to_ref = item.get("to")
            if to_ref is None:
                to_ref = ""
            label = item.get("label") or item.get("Label") or ""
            try:
                from_idx = _parse_index_from_ref(from_ref)
                to_idx = _parse_index_from_ref(to_ref)
                if 0 <= from_idx < n_abs and 0 <= to_idx < n_abs:
                    details.append({"from": from_idx, "to": to_idx, "label": str(label).strip()})
            except (ValueError, TypeError):
                logger.warning("Skipping invalid relationship item: %s", item)
                pass

        logger.info("Extracted relationships: %s", details)
        return {
            "summary": str(summary).strip(),
            "details": details # Store validated, index-based relationships with potentially translated labels
        }

    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        # Structure is now {"summary": str, "details": [{"from": int, "to": int, "label": str}]}
        # Summary and label might be translated if language is not English
        shared["relationships"] = exec_res
        return "default"


class OrderChapters(Node):
    """
    Determine chapter order (abstraction indices) for the tutorial.

    prep: Read abstractions, relationships, project_name, language, use_cache.
    exec: Prompt call_llm for ordered YAML list of index # name; parse and validate all indices present once.
    post: Write chapter_order to shared.
    """

    def prep(self, shared: dict) -> dict:
        abstractions = shared.get("abstractions") or []
        relationships = shared.get("relationships") or {}
        project_name = shared.get("project_name") or "project"
        language = (shared.get("language") or "english").strip().lower()
        use_cache = shared.get("use_cache", True)
        
        # Build abstraction listing
        abstraction_info_for_prompt = []
        for i, a in enumerate(abstractions):
            abstraction_info_for_prompt.append(f"- {i} # {a.get('name', '')}")
        abstraction_listing = "\n".join(abstraction_info_for_prompt)
        
        # Build relationships context
        summary_note = ""
        if language != "english":
            summary_note = f" (Note: Project Summary might be in {language.capitalize()})"
        
        context = f"Project Summary{summary_note}:\n{relationships.get('summary', '')}\n\n"
        context += "Relationships (Indices refer to abstractions above):\n"
        for rel in relationships.get("details") or []:
            from_name = abstractions[rel["from"]]["name"] if rel["from"] < len(abstractions) else ""
            to_name = abstractions[rel["to"]]["name"] if rel["to"] < len(abstractions) else ""
            context += f"- From {rel['from']} ({from_name}) to {rel['to']} ({to_name}): {rel.get('label', '')}\n"
        
        list_lang_note = ""
        if language != "english":
            list_lang_note = f" (Names might be in {language.capitalize()})"
        
        return {
            "abstractions": abstractions,
            "project_name": project_name,
            "language": language,
            "use_cache": use_cache,
            "abstraction_listing": abstraction_listing,
            "context": context,
            "list_lang_note": list_lang_note,
        }

    def exec(self, prep_res: dict) -> list[int]:
        abstractions = prep_res.get("abstractions") or []
        project_name = prep_res.get("project_name") or "project"
        abstraction_listing = prep_res.get("abstraction_listing") or ""
        context = prep_res.get("context") or ""
        use_cache = prep_res.get("use_cache", True)
        list_lang_note = prep_res.get("list_lang_note", "")
        n_abs = len(abstractions)

        prompt = f"""Given the following project abstractions and their relationships for the project `{project_name}`:

Abstractions (Index # Name){list_lang_note}:
{abstraction_listing}

Context about relationships and project summary:
{context}

If you are going to make a tutorial for ```` {project_name} ````, what is the best order to explain these abstractions, from first to last?
Ideally, first explain those that are the most important or foundational, perhaps user-facing concepts or entry points. Then move to more detailed, lower-level implementation details or supporting concepts.

Output the ordered list of abstraction indices, including the name in a comment for clarity. Use the format `idx # AbstractionName`.

```yaml
- 2 # FoundationalConcept
- 0 # CoreClassA
- 1 # CoreClassB (uses CoreClassA)
- ...
```

Now, provide the YAML output:
"""
        # Use cache only if enabled and not retrying
        cache_flag = use_cache and getattr(self, "cur_retry", 0) == 0
        response = call_llm(prompt, use_cache=cache_flag)
        raw = _extract_yaml_block(response)
        data = yaml.safe_load(raw)
        if not isinstance(data, list):
            raise ValueError("LLM did not return a YAML list for chapter order")

        ordered_indices: list[int] = []
        for item in data:
            try:
                idx = _parse_index_from_ref(item)
                if 0 <= idx < n_abs and idx not in ordered_indices:
                    ordered_indices.append(idx)
            except (ValueError, TypeError):
                logger.warning("Skipping invalid chapter order item: %s", item)
                pass

        expected = set(range(n_abs))
        if set(ordered_indices) != expected:
            raise ValueError(f"Chapter order must contain each abstraction index exactly once; got {ordered_indices}, expected {sorted(expected)}")
        logger.info("Determined chapter order: %s", ordered_indices)
        return ordered_indices

    def post(self, shared: dict, prep_res: dict, exec_res: list[int]) -> str:
        shared["chapter_order"] = exec_res
        return "default"


class WriteChapters(BatchNode):
    """
    Generate one chapter per abstraction (BatchNode). Uses chapter_order and abstractions;
    each exec(item) calls call_llm for one chapter; post assigns shared["chapters"].
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.chapters_written_so_far: list[str] = []

    def prep(self, shared: dict) -> list[dict]:
        chapter_order = shared.get("chapter_order") or []
        abstractions = shared.get("abstractions") or []
        files = shared.get("files") or []
        project_name = shared.get("project_name") or "project"
        language = (shared.get("language") or "english").strip().lower()
        use_cache = shared.get("use_cache", True)
        self.chapters_written_so_far = []

        n_files = len(files)
        
        # Create a complete list of all chapters with filenames for linking
        all_chapters = []
        chapter_filenames: dict[int, dict] = {}  # abstraction_index -> {num, name, filename}
        for i, abstraction_index in enumerate(chapter_order):
            if 0 <= abstraction_index < len(abstractions):
                chapter_num = i + 1
                chapter_name = abstractions[abstraction_index].get("name", "")
                # Create safe filename
                safe_name = "".join(c if c.isalnum() else "_" for c in chapter_name).lower()
                filename = f"{i+1:02d}_{safe_name}.md"
                all_chapters.append(f"{chapter_num}. [{chapter_name}]({filename})")
                chapter_filenames[abstraction_index] = {
                    "num": chapter_num,
                    "name": chapter_name,
                    "filename": filename,
                }
        
        full_chapter_listing = "\n".join(all_chapters)
        
        items: list[dict] = []
        for i, abs_idx in enumerate(chapter_order):
            if abs_idx < 0 or abs_idx >= len(abstractions):
                logger.warning("Skipping invalid abstraction index in write chapter: %s", abs_idx)
                continue
            abstraction_details = abstractions[abs_idx]
            name = abstraction_details.get("name") or ""
            desc = abstraction_details.get("description") or ""
            file_indices = abstraction_details.get("files") or []
            file_content_map: dict[str, str] = {}
            for fi in file_indices:
                if 0 <= fi < n_files:
                    path, content = files[fi]
                    file_content_map[f"{fi} # {path}"] = content
            
            # Get previous chapter info for transitions
            prev_chapter = None
            if i > 0:
                prev_idx = chapter_order[i - 1]
                prev_chapter = chapter_filenames.get(prev_idx)
            
            # Get next chapter info for transitions
            next_chapter = None
            if i < len(chapter_order) - 1:
                next_idx = chapter_order[i + 1]
                next_chapter = chapter_filenames.get(next_idx)
            
            items.append({
                "chapter_number": i + 1,
                "abstraction_index": abs_idx,
                "abstraction_name": name,
                "abstraction_description": desc,
                "file_content_map": file_content_map,
                "full_chapter_listing": full_chapter_listing,
                "chapter_filenames": chapter_filenames,
                "prev_chapter": prev_chapter,
                "next_chapter": next_chapter,
                "language": language,
                "project_name": project_name,
                "use_cache": use_cache,
            })
        logger.info("Prepared %s chapters for writing...", len(items))
        return items

    def exec(self, item: dict) -> str:
        name = item.get("abstraction_name") or "Concept"
        desc = item.get("abstraction_description") or ""
        file_content = item.get("file_content_map") or {}
        full_chapter_listing = item.get("full_chapter_listing") or ""
        prev_chapter = item.get("prev_chapter")
        next_chapter = item.get("next_chapter")
        language = item.get("language") or "english"
        project_name = item.get("project_name") or "project"
        num = item.get("chapter_number") or 1
        use_cache = item.get("use_cache", True)

        logger.info("Writing chapter %s: %s", num, name)
        
        # Get summary of chapters written *before* this one
        previous_chapters_summary = "\n---\n".join(self.chapters_written_so_far)
        
        # Prepare file context string
        file_context_str = "\n\n".join(
            f"--- File: {idx_path.split('# ')[1] if '# ' in idx_path else idx_path} ---\n{content}"
            for idx_path, content in file_content.items()
        )
        
        # Add language instruction and context notes only if not English
        language_instruction = ""
        concept_details_note = ""
        structure_note = ""
        prev_summary_note = ""
        instruction_lang_note = ""
        mermaid_lang_note = ""
        code_comment_note = ""
        link_lang_note = ""
        tone_note = ""
        if language != "english":
            lang_cap = language.capitalize()
            language_instruction = f"IMPORTANT: Write this ENTIRE tutorial chapter in **{lang_cap}**. Some input context (like concept name, description, chapter list, previous summary) might already be in {lang_cap}, but you MUST translate ALL other generated content including explanations, examples, technical terms, and potentially code comments into {lang_cap}. DO NOT use English anywhere except in code syntax, required proper nouns, or when specified. The entire output MUST be in {lang_cap}.\n\n"
            concept_details_note = f" (Note: Provided in {lang_cap})"
            structure_note = f" (Note: Chapter names might be in {lang_cap})"
            prev_summary_note = f" (Note: This summary might be in {lang_cap})"
            instruction_lang_note = f" (in {lang_cap})"
            mermaid_lang_note = f" (Use {lang_cap} for labels/text if appropriate)"
            code_comment_note = f" (Translate to {lang_cap} if possible, otherwise keep minimal English for clarity)"
            link_lang_note = f" (Use the {lang_cap} chapter title from the structure above)"
            tone_note = f" (appropriate for {lang_cap} readers)"

        prompt = f"""{language_instruction}Write a very beginner-friendly tutorial chapter (in Markdown format) for the project `{project_name}` about the concept: "{name}". This is Chapter {num}.

Concept Details{concept_details_note}:
- Name: {name}
- Description:
{desc}

Complete Tutorial Structure{structure_note}:
{full_chapter_listing}

Context from previous chapters{prev_summary_note}:
{previous_chapters_summary if previous_chapters_summary else "This is the first chapter."}

Relevant Code Snippets (Code itself remains unchanged):
{file_context_str if file_context_str else "No specific code snippets provided for this abstraction."}

Instructions for the chapter (Generate content in {language.capitalize()} unless specified otherwise):
- Start with a clear heading (e.g., `# Chapter {num}: {name}`). Use the provided concept name.
- If this is not the first chapter, begin with a brief transition from the previous chapter{instruction_lang_note}, referencing it with a proper Markdown link using its name{link_lang_note}.
- Begin with a high-level motivation explaining what problem this abstraction solves{instruction_lang_note}. Start with a central use case as a concrete example. The whole chapter should guide the reader to understand how to solve this use case. Make it very minimal and friendly to beginners.
- If the abstraction is complex, break it down into key concepts. Explain each concept one-by-one in a very beginner-friendly way{instruction_lang_note}.
- Explain how to use this abstraction to solve the use case{instruction_lang_note}. Give example inputs and outputs for code snippets (if the output isn't values, describe at a high level what will happen{instruction_lang_note}).
- Each code block should be BELOW 10 lines! If longer code blocks are needed, break them down into smaller pieces and walk through them one-by-one. Aggressively simplify the code to make it minimal. Use comments{code_comment_note} to skip non-important implementation details. Each code block should have a beginner friendly explanation right after it{instruction_lang_note}.
- Describe the internal implementation to help understand what's under the hood{instruction_lang_note}. First provide a non-code or code-light walkthrough on what happens step-by-step when the abstraction is called{instruction_lang_note}. It's recommended to use a simple sequenceDiagram with a dummy example - keep it minimal with at most 5 participants to ensure clarity. If participant name has space, use: `participant QP as Query Processing`. {mermaid_lang_note}.
- Then dive deeper into code for the internal implementation with references to files. Provide example code blocks, but make them similarly simple and beginner-friendly. Explain{instruction_lang_note}.
- IMPORTANT: When you need to refer to other core abstractions covered in other chapters, ALWAYS use proper Markdown links like this: [Chapter Title](filename.md). Use the Complete Tutorial Structure above to find the correct filename and the chapter title{link_lang_note}. Translate the surrounding text.
- Use mermaid diagrams to illustrate complex concepts (```mermaid``` format). {mermaid_lang_note}.
- Heavily use analogies and examples throughout{instruction_lang_note} to help beginners understand.
- End the chapter with a brief conclusion that summarizes what was learned{instruction_lang_note} and provides a transition to the next chapter{instruction_lang_note}. If there is a next chapter, use a proper Markdown link: [Next Chapter Title](next_chapter_filename){link_lang_note}.
- Ensure the tone is welcoming and easy for a newcomer to understand{tone_note}.
- Output *only* the Markdown content for this chapter.

Now, directly provide a super beginner-friendly Markdown output (DON'T need ```markdown``` tags):
"""
        # Use cache only if enabled and not retrying
        cache_flag = use_cache and getattr(self, "cur_retry", 0) == 0
        chapter_content = call_llm(prompt, use_cache=cache_flag)
        
        # Basic validation/cleanup - ensure proper heading
        actual_heading = f"# Chapter {num}: {name}"
        if not chapter_content.strip().startswith(f"# Chapter {num}"):
            lines = chapter_content.strip().split("\n")
            if lines and lines[0].strip().startswith("#"):
                lines[0] = actual_heading
                chapter_content = "\n".join(lines)
            else:
                chapter_content = f"{actual_heading}\n\n{chapter_content}"
        
        # Add the generated content to our temporary list for the next iteration's context
        self.chapters_written_so_far.append(chapter_content)
        return chapter_content

    def post(self, shared: dict, prep_res: list[dict], exec_res_list: list[str]) -> str:
        shared["chapters"] = exec_res_list
        self.chapters_written_so_far = []
        logger.info("Written all %s chapters.", len(exec_res_list))
        return "default"


class CombineTutorial(Node):
    """
    Build Mermaid diagram, index.md, and chapter files; write to output_dir/project_name.
    post: set shared["final_output_dir"].
    """

    def prep(self, shared: dict) -> dict:
        project_name = shared.get("project_name") or "project"
        relationships = shared.get("relationships") or {}
        chapter_order = shared.get("chapter_order") or []
        abstractions = shared.get("abstractions") or []
        chapters = shared.get("chapters") or []
        repo_url = shared.get("repo_url") or ""
        output_dir = (self.params.get("output_dir", shared.get("output_dir", "output")) or "output").strip()
        details = relationships.get("details") or []
        summary = relationships.get("summary") or ""

        out_path = os.path.join(output_dir, project_name.replace(os.sep, "_").strip() or "output")
        
        # --- Generate Mermaid Diagram ---
        mermaid_lines = ["flowchart TD"]
        
        # First, add nodes for each abstraction
        for i, abstr in enumerate(abstractions):
            node_id = f"A{i}"
            # Sanitize name for Mermaid
            sanitized_name = abstr.get("name", "").replace('"', "'")
            mermaid_lines.append(f'    {node_id}["{sanitized_name}"]')
        
        # Then add edges for relationships
        for rel in details:
            from_node_id = f"A{rel.get('from', 0)}"
            to_node_id = f"A{rel.get('to', 0)}"
            # Sanitize and truncate label
            edge_label = rel.get("label", "").replace('"', '"').replace("\n", " ")
            max_label_len = 30
            if len(edge_label) > max_label_len:
                edge_label = edge_label[:max_label_len - 3] + "..."
            mermaid_lines.append(f'    {from_node_id} -->|"{edge_label}"| {to_node_id}')
        
        mermaid_block = "\n".join(mermaid_lines)

        # --- Prepare index.md content ---
        index_content = f"# Tutorial: {project_name}\n\n"
        index_content += f"{summary}\n\n"
        
        # Add source repository link if available
        if repo_url:
            index_content += f"**Source Repository:** [{repo_url}]({repo_url})\n\n"
        
        # Add Mermaid diagram
        index_content += "```mermaid\n"
        index_content += mermaid_block + "\n"
        index_content += "```\n\n"
        
        index_content += "## Chapters\n\n"

        chapter_files: list[dict[str, str]] = []
        for i, idx in enumerate(chapter_order):
            if 0 <= idx < len(abstractions) and i < len(chapters):
                name = abstractions[idx].get("name", f"Chapter {i+1}")
                # Sanitize name for filename
                safe_name = "".join(c if c.isalnum() else "_" for c in name).lower()
                fn = f"{i+1:02d}_{safe_name}.md"
                index_content += f"{i+1}. [{name}]({fn})\n"
                
                # Add attribution to chapter content
                chapter_content = chapters[i]
                if not chapter_content.endswith("\n\n"):
                    chapter_content += "\n\n"
                chapter_content += "---\n\nGenerated by [Code IQ](https://github.com/adityasoni99/Code-IQ)"
                
                chapter_files.append({"filename": fn, "content": chapter_content})
            else:
                logger.warning("Warning: Mismatch between chapter order, abstractions, or content at index %s (abstraction index %s). Skipping file generation for this entry.", i, idx)
        
        # Add attribution to index content
        index_content += "\n\n---\n\nGenerated by [Code IQ](https://github.com/adityasoni99/Code-IQ)"

        return {
            "output_path": out_path,
            "index_content": index_content,
            "chapter_files": chapter_files,
            "repo_url": repo_url,
        }

    def exec(self, prep_res: dict) -> str:
        out_path = prep_res.get("output_path") or ""
        index_content = prep_res.get("index_content") or ""
        chapter_files = prep_res.get("chapter_files") or []
        os.makedirs(out_path, exist_ok=True)
        index_file = os.path.join(out_path, "index.md")
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(index_content)
        for ch in chapter_files:
            fn = ch.get("filename") or "chapter.md"
            content = ch.get("content") or ""
            with open(os.path.join(out_path, fn), "w", encoding="utf-8") as f:
                f.write(content)
        return out_path

    def post(self, shared: dict, prep_res: dict, exec_res: str) -> str:
        shared["final_output_dir"] = exec_res
        logger.info("CombineTutorial: output_dir=%s", exec_res)
        return "default"


def _extract_mermaid_blocks(text: str) -> list[str]:
    """Extract all ```mermaid ... ``` blocks from markdown text."""
    pattern = r"```mermaid\s*\n(.*?)\n```"
    return re.findall(pattern, text, re.DOTALL)


def _extract_first_paragraph(text: str) -> str:
    """Extract first non-empty paragraph (strip markdown headers)."""
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            continue
        if line:
            return line[:500]
    return ""


def _build_output_tree(output_dir: Path) -> list[dict]:
    """Walk output_dir, find all index.md; return flat list of {path, rel_path, name, content, mermaid, summary}."""
    result = []
    output_dir = Path(output_dir).resolve()
    if not output_dir.exists():
        return result
    for d in output_dir.rglob("*"):
        if not d.is_dir():
            continue
        index_md = d / "index.md"
        if not index_md.is_file():
            continue
        try:
            content = index_md.read_text(encoding="utf-8")
        except Exception:
            content = ""
        mermaid_blocks = _extract_mermaid_blocks(content)
        mermaid = mermaid_blocks[0] if mermaid_blocks else ""
        summary = _extract_first_paragraph(content)
        try:
            rel = d.relative_to(output_dir)
        except ValueError:
            rel = d.name
        rel_path = str(rel).replace("\\", "/")
        name = d.name
        result.append({
            "path": str(d),
            "rel_path": rel_path,
            "name": name,
            "content": content,
            "mermaid": mermaid,
            "summary": summary,
        })
    return sorted(result, key=lambda x: x["rel_path"])


def _flat_tree_to_nested(flat: list[dict]) -> list[dict]:
    """Convert flat list of nodes (by rel_path) into nested tree with children."""
    by_rel = {n["rel_path"]: n for n in flat}
    for node in flat:
        rel = node["rel_path"]
        node["slug"] = rel.replace("/", "_")
        node["children"] = []
    for node in flat:
        rel = node["rel_path"]
        if "/" in rel:
            prefix = rel.rsplit("/", 1)[0]
            parent = by_rel.get(prefix)
            if parent is not None:
                parent["children"].append(node)
    return [n for n in flat if "/" not in n["rel_path"]]


class GenerateHierarchicalView(Node):
    """
    Build tree.json, master_index.md, and self-contained master_index.html from output tree.
    Single HTML with TREE/PAGES/DIAGRAMS JSON, marked.js + mermaid.js, sidebar + breadcrumb.
    """

    def prep(self, shared: dict) -> dict:
        output_dir = shared.get("output_dir", "output")
        out_path = Path(output_dir).resolve()
        flat = _build_output_tree(out_path)
        nested = _flat_tree_to_nested(flat)
        pages = {n["slug"]: n["content"] for n in flat}
        diagrams = {n["slug"]: n["mermaid"] for n in flat}
        return {
            "output_dir": output_dir,
            "output_tree": nested,
            "flat": flat,
            "pages": pages,
            "diagrams": diagrams,
        }

    def exec(self, prep_res: dict) -> dict:
        import json as _json
        tree = prep_res.get("output_tree") or []
        flat = prep_res.get("flat") or []
        pages = prep_res.get("pages") or {}
        diagrams = prep_res.get("diagrams") or {}
        # tree.json (for programmatic use)
        def to_serializable(n):
            return {
                "name": n["name"],
                "slug": n.get("slug", n["rel_path"].replace("/", "_")),
                "path": n["rel_path"],
                "mermaid": n.get("mermaid", ""),
                "summary": n.get("summary", ""),
                "children": [to_serializable(c) for c in n.get("children", [])],
            }
        tree_json = [to_serializable(n) for n in tree]
        tree_json_str = _json.dumps(tree_json, indent=2)
        # master_index.md: Mermaid subgraphs with click links
        md_lines = ["# Master Tutorial Index\n"]
        for n in flat:
            slug = n.get("slug", n["rel_path"].replace("/", "_"))
            md_lines.append(f"- [{n['name']}]({n['rel_path']}/index.md)\n")
        master_md = "\n".join(md_lines)
        if flat:
            md_lines = ["# Master Tutorial Index\n", "```mermaid", "flowchart LR"]
            for n in flat:
                slug = n.get("slug", n["rel_path"].replace("/", "_"))
                safe = slug.replace('"', "'")
                md_lines.append(f'    {safe}["{n["name"]}"]')
            md_lines.append("```")
            master_md = "\n".join(md_lines)
        # master_index.html: self-contained SPA
        pages_escaped = _json.dumps(pages).replace("<", "\\u003c").replace(">", "\\u003e")
        diagrams_escaped = _json.dumps(diagrams).replace("<", "\\u003c").replace(">", "\\u003e")
        tree_escaped = _json.dumps(tree_json).replace("<", "\\u003c").replace(">", "\\u003e")
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Master Tutorial Index</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body {{ font-family: sans-serif; margin: 0; display: flex; min-height: 100vh; }}
    #sidebar {{ width: 240px; background: #f5f5f5; padding: 1rem; overflow-y: auto; }}
    #sidebar ul {{ list-style: none; padding-left: 1rem; }}
    #sidebar a {{ color: #0366d6; text-decoration: none; }}
    #sidebar a:hover {{ text-decoration: underline; }}
    #content {{ flex: 1; padding: 1rem 2rem; overflow-y: auto; }}
    #breadcrumb {{ margin-bottom: 1rem; color: #666; }}
    #breadcrumb a {{ color: #0366d6; }}
  </style>
</head>
<body>
  <nav id="sidebar"><ul id="tree-nav"></ul></nav>
  <main>
    <div id="breadcrumb"></div>
    <div id="content"></div>
  </main>
  <script>
    var TREE = {tree_escaped};
    var PAGES = {pages_escaped};
    var DIAGRAMS = {diagrams_escaped};
    function renderNav(children, ul) {{
      if (!ul) ul = document.createElement("ul");
      ul.innerHTML = "";
      (children || []).forEach(function(n) {{
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = "#" + n.slug;
        a.textContent = n.name;
        a.onclick = function(e) {{ e.preventDefault(); location.hash = n.slug; render(); }};
        li.appendChild(a);
        if (n.children && n.children.length) {{
          var sub = renderNav(n.children, null);
          li.appendChild(sub);
        }}
        ul.appendChild(li);
      }});
      return ul;
    }}
    function render() {{
      var slug = (location.hash || "#").slice(1) || (TREE[0] && TREE[0].slug);
      if (!slug && TREE.length) slug = TREE[0].slug;
      document.getElementById("tree-nav").innerHTML = "";
      var rootUl = document.createElement("ul");
      renderNav(TREE, rootUl);
      document.getElementById("tree-nav").appendChild(rootUl);
      var content = document.getElementById("content");
      var breadcrumb = document.getElementById("breadcrumb");
      if (PAGES[slug]) {{
        content.innerHTML = marked.parse(PAGES[slug]);
        content.querySelectorAll("code.language-mermaid").forEach(function(el) {{
          el.classList.add("mermaid");
          if (el.parentNode) el.parentNode.classList.add("mermaid");
        }});
        if (typeof mermaid !== "undefined" && mermaid.run)
          mermaid.run({{ nodes: content.querySelectorAll(".mermaid") }});
      }} else {{
        content.innerHTML = "<p>Select a tutorial from the sidebar.</p>";
      }}
      breadcrumb.innerHTML = "<a href=\"#\">Home</a> &rarr; " + (slug || "");
    }}
    window.onhashchange = render;
    document.addEventListener("DOMContentLoaded", render);
  </script>
</body>
</html>"""
        return {"md": master_md, "html": html, "tree_json": tree_json_str}

    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        output_dir = prep_res.get("output_dir", "output")
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "master_index.md").write_text(exec_res.get("md") or "", encoding="utf-8")
        (out_path / "master_index.html").write_text(exec_res.get("html") or "", encoding="utf-8")
        (out_path / "tree.json").write_text(exec_res.get("tree_json") or "[]", encoding="utf-8")
        master_path = out_path / "master_index.html"
        shared["master_index_path"] = str(master_path)
        return "default"
