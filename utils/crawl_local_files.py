"""
Crawl a local directory and return file path -> content.

Used by FetchRepo when local_dir is provided.
"""

import fnmatch
import os
from typing import Set


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "out",
    "coverage",
    ".next",
    ".nuxt",
    ".parcel-cache",
    ".turbo",
    "target",
    ".gradle",
    ".cache",
}

SKIP_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".7z",
    ".rar",
    ".mp4",
    ".mov",
    ".mp3",
    ".wav",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".ds_store",
}


def crawl_local_files(
    directory: str,
    max_file_size: int = 100_000,
    use_relative_paths: bool = True,
    include_patterns: Set[str] | None = None,
    exclude_patterns: Set[str] | None = None,
) -> dict:
    """
    Walk a directory and read file contents into a path -> content dict.

    Args:
        directory: Root directory to crawl.
        max_file_size: Skip files larger than this (bytes). Default 100_000.
        use_relative_paths: If True, keys in files are relative to directory; else absolute.
        include_patterns: If non-empty, only include files whose path matches any glob (e.g. {"*.py", "*.md"}).
        exclude_patterns: If non-empty, exclude files whose path matches any glob (e.g. {"*.pyc", "__pycache__"}).

    Returns:
        Dict with key "files": dict[str, str] mapping file path to content.
        Binary or oversized files are skipped; decode errors result in skip.
    """
    directory = os.path.abspath(directory)
    include_patterns = include_patterns or set()
    exclude_patterns = exclude_patterns or set()
    files: dict = {}

    for root, dirs, filenames in os.walk(directory, topdown=True):
        dirs[:] = [d for d in dirs if not _should_skip_dir(d)]
        for name in filenames:
            full_path = os.path.join(root, name)
            try:
                stat = os.stat(full_path)
            except OSError:
                continue
            if stat.st_size > max_file_size:
                continue
            rel = os.path.relpath(full_path, directory)
            if _is_hidden_path(rel):
                continue
            if _has_skip_ext(rel):
                continue
            if _excluded(rel, include_patterns, exclude_patterns):
                continue
            try:
                with open(full_path, "r", encoding="utf-8", errors="strict") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            key = rel if use_relative_paths else full_path
            files[key] = content

    return {"files": files}


def _excluded(rel_path: str, include: Set[str], exclude: Set[str]) -> bool:
    """Return True if rel_path should be excluded (not included or explicitly excluded)."""
    if exclude and any(fnmatch.fnmatch(rel_path, p) for p in exclude):
        return True
    if include and not any(fnmatch.fnmatch(rel_path, p) for p in include):
        return True
    return False


def _should_skip_dir(name: str) -> bool:
    if name.startswith("."):
        return True
    return name in SKIP_DIRS


def _is_hidden_path(rel_path: str) -> bool:
    parts = rel_path.split(os.sep)
    return any(p.startswith(".") for p in parts)


def _has_skip_ext(rel_path: str) -> bool:
    lower = rel_path.lower()
    return any(lower.endswith(ext) for ext in SKIP_EXTS)
