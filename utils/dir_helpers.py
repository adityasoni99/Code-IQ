"""
Directory helpers for recursive subfolder discovery and checkpoint detection.

Used by DiscoverLeafFolders and by the deprecated run_tutorials_for_subfolders_recursive.py.
"""

from pathlib import Path
from typing import Union

# Pipeline writes output_dir/project_name/index.md when done
CHECKPOINT_MARKER = "index.md"


def count_files_under(path: Path) -> int:
    """Return the number of files under `path` (recursively). Directories are not counted."""
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += 1
    except OSError:
        pass
    return total


def has_direct_subdirs(path: Path, skip_hidden: bool = True) -> bool:
    """Return True if `path` has at least one direct subdirectory."""
    for d in path.iterdir():
        if d.is_dir() and (not skip_hidden or not d.name.startswith(".")):
            return True
    return False


def get_direct_subdirs(path: Path, skip_hidden: bool) -> list[Path]:
    """Return sorted list of direct subdirectories."""
    return sorted(
        d
        for d in path.iterdir()
        if d.is_dir() and (not skip_hidden or not d.name.startswith("."))
    )


def is_completed(output_dir: Union[Path, str], project_name: str) -> bool:
    """True if a completed tutorial exists at output_dir/project_name (has index.md)."""
    return (Path(output_dir) / project_name / CHECKPOINT_MARKER).is_file()
