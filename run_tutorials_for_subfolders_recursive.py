#!/usr/bin/env python3
"""
Run Code-IQ tutorial pipeline for each subfolder of given parent folder(s), with recursion.

If a subfolder has more than --file-threshold files (default 100) and has its own
subfolders, the script recurses into it and runs the pipeline for each of those
subfolders instead of running once for the whole subfolder. This keeps prompts
and run sizes manageable for large trees.

Output is written under CodeIQTut/ with the same hierarchy as under the workspace.

Checkpoint/resume: by default the script skips subfolders that already have
output (a completed run has <output_base>/.../index.md). Use --list-status to
see what is done vs pending; use --no-resume to run everything (overwrite).

When a pipeline run fails (e.g. "Failed to fetch files" for empty/skip-only
folders), the script skips that folder and continues by default. Use --fail-fast
to exit on first failure.

Usage:
  python run_tutorials_for_subfolders_recursive.py ~/workspace/Offercomparison
  python run_tutorials_for_subfolders_recursive.py ~/workspace/AgentLock
  python run_tutorials_for_subfolders_recursive.py --list-status ~/workspace/Offercomparison
  python run_tutorials_for_subfolders_recursive.py --no-resume ~/workspace/Offercomparison
  # Default: recurse when a subfolder has >100 files and has subfolders
  python run_tutorials_for_subfolders_recursive.py ~/workspace/Offercomparison
  # Use 50 as threshold
  python run_tutorials_for_subfolders_recursive.py --file-threshold 50 ~/workspace/Offercomparison
  # See what would run (including recursion decisions)
  python run_tutorials_for_subfolders_recursive.py --dry-run ~/workspace/Offercomparison
"""

import argparse
import subprocess
import sys
from pathlib import Path

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


def is_completed(output_dir: Path, project_name: str) -> bool:
    """True if a completed tutorial exists at output_dir/project_name (has index.md)."""
    return (output_dir / project_name / CHECKPOINT_MARKER).is_file()


def process_parent(
    parent: Path,
    output_dir: Path,
    *,
    repo_root: Path,
    file_threshold: int,
    dry_run: bool,
    skip_hidden: bool,
    resume: bool,
    list_status: bool,
    skip_failures: bool,
) -> int:
    """
    Process a parent directory: for each direct subdir, either run the pipeline
    for that subdir or recurse into it if it has > file_threshold files and subdirs.
    When resume is True, skips subdirs that already have output (index.md).
    When list_status is True, only prints DONE/PENDING for each leaf and does not run.
    When skip_failures is True, on pipeline failure log and continue; else return exit code.
    Returns 0 on success, non-zero on first failure (if not skipped).
    """
    subdirs = get_direct_subdirs(parent, skip_hidden)
    if not subdirs:
        return 0

    for subdir in subdirs:
        local_dir = subdir.resolve()
        nfiles = count_files_under(local_dir)
        has_subdirs = has_direct_subdirs(local_dir, skip_hidden)

        if nfiles > file_threshold and has_subdirs:
            # Recurse: use this subdir as the new parent, output base = output_dir / subdir.name
            next_output = output_dir / subdir.name
            if not list_status:
                print(f"\n>>> Recursing into {local_dir} (files={nfiles}, has subdirs)")
            ret = process_parent(
                local_dir,
                next_output,
                repo_root=repo_root,
                file_threshold=file_threshold,
                dry_run=dry_run,
                skip_hidden=skip_hidden,
                resume=resume,
                list_status=list_status,
                skip_failures=skip_failures,
            )
            if ret != 0:
                return ret
            continue

        # Leaf: run pipeline for this subdir (or skip if done / list status)
        out_path = output_dir / subdir.name
        done = is_completed(output_dir, subdir.name)

        if list_status:
            status = "DONE   " if done else "PENDING"
            print(f"  {status}  {out_path}  <-  {local_dir}")
            continue

        if resume and done:
            print(f"\nSkipping (already done): {local_dir}  ->  {out_path}")
            continue

        cmd = [
            sys.executable,
            str(repo_root / "main.py"),
            "--local-dir",
            str(local_dir),
            "--output-dir",
            str(output_dir),
        ]
        if dry_run:
            print("Would run:", " ".join(cmd))
            continue
        print(f"\n--- {local_dir.name} (files={nfiles}) ---")
        ret = subprocess.run(cmd, cwd=str(repo_root))
        if ret.returncode != 0:
            if skip_failures:
                print(
                    f"Warning: skipping after failure (exit {ret.returncode}): {local_dir}",
                    file=sys.stderr,
                )
            else:
                print(f"Failed: {local_dir.name} (exit {ret.returncode})", file=sys.stderr)
                return ret.returncode

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Code-IQ for each subfolder of the given parent(s), recursing into "
        "subfolders that have more than FILE_THRESHOLD files and their own subfolders. "
        "Output hierarchy is preserved under CodeIQTut/."
    )
    parser.add_argument(
        "parent_dirs",
        nargs="+",
        help="Parent directory (e.g. ~/workspace/main/magneto). "
        "Each direct subdirectory will be processed (or recursed into).",
    )
    parser.add_argument(
        "--file-threshold",
        type=int,
        default=100,
        metavar="N",
        help="If a subfolder has more than N files and has subfolders, recurse into it (default: 100).",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Workspace root used to compute output path (default: ~/workspace).",
    )
    parser.add_argument(
        "--output-base",
        type=str,
        default=None,
        help="Base directory for output (default: <repo_root>/CodeIQTut).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands only, do not run.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="Disable checkpoint/resume; run all and overwrite existing output (default: resume by skipping done).",
    )
    parser.add_argument(
        "--list-status",
        action="store_true",
        help="Only list checkpoint status: DONE (has index.md) vs PENDING for each subfolder, then exit.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Exit on first pipeline failure (default: skip failed folder and continue).",
    )
    parser.add_argument(
        "--no-skip-hidden",
        action="store_false",
        dest="skip_hidden",
        help="Include subdirectories whose names start with '.' (default: skip them).",
    )
    parser.set_defaults(skip_hidden=True, resume=True, skip_failures=True)
    args = parser.parse_args()
    skip_failures = not args.fail_fast

    repo_root = Path(__file__).resolve().parent
    output_base = Path(args.output_base).resolve() if args.output_base else repo_root / "CodeIQTut"

    for parent_arg in args.parent_dirs:
        parent = Path(parent_arg).expanduser().resolve()
        if not parent.is_dir():
            print(f"Error: not a directory: {parent}", file=sys.stderr)
            return 1

        workspace_root = Path(args.workspace).expanduser().resolve() if args.workspace else None
        if workspace_root is None:
            workspace_root = Path.home() / "workspace"
        else:
            workspace_root = workspace_root.resolve()

        try:
            rel = parent.relative_to(workspace_root)
        except ValueError:
            rel = Path(parent.name)
        output_dir = output_base / rel

        subdirs = get_direct_subdirs(parent, args.skip_hidden)
        if not subdirs:
            print(f"No subdirectories under {parent}, skipping.")
            continue

        if args.list_status:
            print(f"Checkpoint status (output base: {output_dir})")
            print(f"  DONE   = has {CHECKPOINT_MARKER} (will skip with --resume)")
            print(f"  PENDING = not yet run (or --no-resume)")
        else:
            print(f"Parent: {parent}")
            print(f"Output base: {output_dir}")
            print(f"Resume: {args.resume} (skip completed)")
            print(f"File threshold: {args.file_threshold} (recurse if subfolder has more files and has subdirs)")
            print(f"Subfolders ({len(subdirs)}): {[d.name for d in subdirs]}")

        ret = process_parent(
            parent,
            output_dir,
            repo_root=repo_root,
            file_threshold=args.file_threshold,
            dry_run=args.dry_run,
            skip_hidden=args.skip_hidden,
            resume=args.resume,
            list_status=args.list_status,
            skip_failures=skip_failures,
        )
        if ret != 0:
            return ret

    return 0


if __name__ == "__main__":
    sys.exit(main())
