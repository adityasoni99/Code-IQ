"""
Crawl a GitHub repository and return file path -> content via GitHub API.

Used by FetchRepo when repo_url is provided.
"""

import base64
import fnmatch
import os
import re
import tempfile
import time
from typing import Set

import git
import requests


GITHUB_API = "https://api.github.com"
DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

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


def _parse_repo_url(repo_url: str) -> tuple:
    """Extract (owner, repo) from URL. Raises ValueError if not parseable."""
    repo_url = repo_url.strip().rstrip("/")
    # https://github.com/owner/repo or git@github.com:owner/repo.git
    m = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?$", repo_url, re.I)
    if m:
        return (m.group(1), m.group(2).removesuffix(".git"))
    m = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if m:
        return (m.group(1), m.group(2).removesuffix(".git"))
    raise ValueError(f"Cannot parse repo URL: {repo_url!r}")


def _excluded(path: str, include: Set[str], exclude: Set[str]) -> bool:
    if exclude and any(fnmatch.fnmatch(path, p) for p in exclude):
        return True
    if include and not any(fnmatch.fnmatch(path, p) for p in include):
        return True
    return False


def _should_skip_path(path: str) -> bool:
    if _is_hidden_path(path):
        return True
    if _has_skip_dir(path):
        return True
    if _has_skip_ext(path):
        return True
    return False


def _is_hidden_path(path: str) -> bool:
    parts = path.split("/")
    return any(p.startswith(".") for p in parts)


def _has_skip_dir(path: str) -> bool:
    parts = path.split("/")
    return any(p in SKIP_DIRS for p in parts)


def _has_skip_ext(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in SKIP_EXTS)


def _get_blob_with_retry(
    owner: str,
    repo: str,
    sha: str,
    headers: dict,
    max_retries: int = 3,
) -> requests.Response:
    """GET blob with retries on 403 rate limit (backoff using Retry-After or exponential)."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs/{sha}"
    for attempt in range(max_retries):
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 403 or attempt == max_retries - 1:
            return resp
        retry_after = resp.headers.get("Retry-After")
        reset = resp.headers.get("X-RateLimit-Reset")
        if retry_after and retry_after.isdigit():
            wait = int(retry_after)
        elif reset and reset.isdigit():
            wait = max(int(reset) - int(time.time()), 0) + 1
        else:
            wait = (2 ** attempt) * 60  # 1m, 2m, 4m
        time.sleep(min(wait, 3600))
    return resp


def _request_with_rate_limit_retry(
    method: str,
    url: str,
    headers: dict,
    params: dict | None = None,
    max_retries: int = 3,
) -> requests.Response:
    """Request with rate-limit-aware retries (honors Retry-After or X-RateLimit-Reset)."""
    for attempt in range(max_retries):
        resp = requests.request(method, url, headers=headers, params=params, timeout=30)
        if resp.status_code != 403:
            return resp
        body = (resp.text or "").lower()
        if "rate limit" not in body and "rate-limit" not in body:
            return resp
        retry_after = resp.headers.get("Retry-After")
        reset = resp.headers.get("X-RateLimit-Reset")
        wait = None
        if retry_after and retry_after.isdigit():
            wait = int(retry_after)
        elif reset and reset.isdigit():
            wait = max(int(reset) - int(time.time()), 0) + 1
        if wait is None:
            wait = (2 ** attempt) * 60
        time.sleep(min(wait, 3600))
    return resp


def _crawl_github_files_locally(
    repo_url: str,
    max_file_size: int = 100_000,
    use_relative_paths: bool = True,
    include_patterns: Set[str] | None = None,
    exclude_patterns: Set[str] | None = None,
) -> dict:
    """
    Fallback: Clone repo to temp dir and crawl files locally.
    Used when GitHub API is rate-limited or unavailable.
    """
    include_patterns = include_patterns or set()
    exclude_patterns = exclude_patterns or set()
    
    def should_include_file(file_path: str, file_name: str) -> bool:
        """Check if file should be included based on patterns."""
        if include_patterns:
            if not any(fnmatch.fnmatch(file_name, pattern) for pattern in include_patterns):
                return False
        if exclude_patterns:
            if any(fnmatch.fnmatch(file_path, pattern) for pattern in exclude_patterns):
                return False
        return True
    
    files: dict = {}
    stats = {
        "files_count": 0,
        "skipped_size": 0,
        "skipped_pattern": 0,
        "skipped_decode": 0,
        "truncated": False,
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            print(f"Cloning {repo_url} to temporary directory...")
            repo = git.Repo.clone_from(repo_url, tmpdir, depth=1)  # Shallow clone
        except Exception as e:
            raise ValueError(f"Failed to clone repository: {e}")
        
        # Walk all files in the cloned repo
        for root, dirs, filenames in os.walk(tmpdir):
            # Skip .git and other unwanted directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            
            for filename in filenames:
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, tmpdir)
                
                # Skip files with unwanted extensions
                if _has_skip_ext(rel_path):
                    stats["skipped_pattern"] += 1
                    continue
                
                # Check file size
                try:
                    file_size = os.path.getsize(abs_path)
                except OSError:
                    continue
                
                if file_size > max_file_size:
                    stats["skipped_size"] += 1
                    continue
                
                # Check include/exclude patterns
                if not should_include_file(rel_path, filename):
                    stats["skipped_pattern"] += 1
                    continue
                
                # Read file content
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    key = rel_path if use_relative_paths else f"{repo_url.split('/')[-1]}/{rel_path}"
                    files[key] = content
                    stats["files_count"] += 1
                    
                except (UnicodeDecodeError, OSError):
                    stats["skipped_decode"] += 1
                    continue
    
    return {"files": files, "stats": stats}


def crawl_github_files(
    repo_url: str,
    token: str | None = None,
    max_file_size: int = 100_000,
    use_relative_paths: bool = True,
    include_patterns: Set[str] | None = None,
    exclude_patterns: Set[str] | None = None,
) -> dict:
    """
    List and fetch file contents from a GitHub repo via Git Trees + Blobs API.

    Args:
        repo_url: GitHub repo URL (https://github.com/owner/repo or git@github.com:owner/repo.git).
        token: Optional GitHub token for higher rate limits and private repos.
        max_file_size: Skip blobs larger than this (bytes). Default 100_000.
        use_relative_paths: If True, keys in files are path relative to repo root; else full path.
        include_patterns: If non-empty, only include paths matching any glob.
        exclude_patterns: If non-empty, exclude paths matching any glob.

    Returns:
        Dict with "files": dict[str, str] (path -> content) and "stats": dict with
        files_count, skipped_size, skipped_pattern, skipped_decode, truncated.
    """
    owner, repo = _parse_repo_url(repo_url)
    include_patterns = include_patterns or set()
    exclude_patterns = exclude_patterns or set()
    headers = {**DEFAULT_HEADERS}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    files: dict = {}
    stats = {
        "files_count": 0,
        "skipped_size": 0,
        "skipped_pattern": 0,
        "skipped_decode": 0,
        "truncated": False,
    }

    # Try GitHub API first
    try:
        # Get tree for default branch (use branch name as tree_sha)
        repo_resp = _request_with_rate_limit_retry(
            "GET",
            f"{GITHUB_API}/repos/{owner}/{repo}",
            headers=headers,
            max_retries=3,
        )
        repo_resp.raise_for_status()
        default_branch = repo_resp.json().get("default_branch", "main")

        tree_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
        tree_resp = _request_with_rate_limit_retry(
            "GET",
            tree_url,
            headers=headers,
            max_retries=3,
        )
        tree_resp.raise_for_status()
        tree_data = tree_resp.json()
        stats["truncated"] = tree_data.get("truncated", False)
        tree = tree_data.get("tree") or []
    
    except (requests.RequestException, requests.HTTPError) as e:
        # If API fails, try local cloning fallback for public repos
        print(f"GitHub API failed ({e}), attempting local clone fallback...")
        if not token:
            print("No token provided - trying to clone public repo locally")
        try:
            return _crawl_github_files_locally(
                repo_url=repo_url,
                max_file_size=max_file_size,
                use_relative_paths=use_relative_paths,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
        except Exception as clone_error:
            print(f"Local clone fallback also failed: {clone_error}")
            if "rate limit" in str(e).lower():
                raise requests.HTTPError(
                    f"GitHub API rate limit exceeded and local clone failed. "
                    f"Set GITHUB_TOKEN for higher limits or ensure git access to the repo: {clone_error}",
                    response=getattr(e, 'response', None),
                )
            raise e

    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        size = item.get("size", 0)
        if size > max_file_size:
            stats["skipped_size"] += 1
            continue
        if _should_skip_path(path):
            stats["skipped_pattern"] += 1
            continue
        if _excluded(path, include_patterns, exclude_patterns):
            stats["skipped_pattern"] += 1
            continue
        sha = item.get("sha")
        if not sha:
            continue
        blob_resp = _get_blob_with_retry(owner, repo, sha, headers, max_retries=3)
        if blob_resp.status_code == 403 and "rate limit" in (blob_resp.text or "").lower():
            raise requests.HTTPError(
                "403 GitHub API rate limit exceeded. Set GITHUB_TOKEN for higher limits (see README).",
                response=blob_resp,
            )
        blob_resp.raise_for_status()
        blob = blob_resp.json()
        content_b64 = blob.get("content")
        encoding = blob.get("encoding", "utf-8")
        if not content_b64:
            stats["skipped_decode"] += 1
            continue
        try:
            raw = base64.b64decode(content_b64, validate=True)
            content = raw.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError):
            stats["skipped_decode"] += 1
            continue
        key = path if use_relative_paths else f"{owner}/{repo}/{path}"
        files[key] = content
        stats["files_count"] += 1

    return {"files": files, "stats": stats}
