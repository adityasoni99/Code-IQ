"""
Code-IQ — CLI entrypoint.

Runs the pipeline flow with shared store initialized from defaults and CLI args.
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from shared_schema import default_shared_store

load_dotenv()
from flow import create_full_flow, create_parallel_recursive_flow, create_recursive_flow

logger = logging.getLogger("codebase_knowledge_builder")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. Requires one of --repo-url, --local-dir, or --parent-dirs."""
    p = argparse.ArgumentParser(
        prog="codebase-knowledge-builder",
        description="Generate a structured tutorial from a GitHub repo or local directory.",
    )
    p.add_argument(
        "--repo-url",
        type=str,
        default=None,
        help="GitHub repository URL (e.g. https://github.com/owner/repo).",
    )
    p.add_argument(
        "--local-dir",
        type=str,
        default=None,
        help="Local directory path to crawl (alternative to --repo-url).",
    )
    p.add_argument(
        "--parent-dirs",
        nargs="+",
        type=str,
        default=None,
        metavar="DIR",
        help="Parent directory(ies) to recurse (run tutorial per subfolder). Mutually exclusive with --repo-url/--local-dir.",
    )
    p.add_argument(
        "--file-threshold",
        type=int,
        default=100,
        metavar="N",
        help="Recurse into subfolders with more than N files (default: 100). Only with --parent-dirs.",
    )
    p.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="Disable checkpoint/resume; process all folders (only with --parent-dirs).",
    )
    p.add_argument(
        "--parallel",
        type=int,
        default=0,
        metavar="N",
        help="Run up to N folders in parallel (0 = sequential). Only with --parent-dirs.",
    )
    p.add_argument(
        "--project-name",
        type=str,
        default=None,
        help="Project name for output (default: derived from repo URL or directory).",
    )
    p.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Base directory for output (default: output).",
    )
    p.add_argument(
        "--language",
        type=str,
        default="english",
        help="Tutorial language (default: english).",
    )
    args = p.parse_args(argv)
    if args.parent_dirs and (args.repo_url or args.local_dir):
        p.error("--parent-dirs is mutually exclusive with --repo-url and --local-dir.")
    if not args.parent_dirs and not args.repo_url and not args.local_dir:
        p.error("One of --repo-url, --local-dir, or --parent-dirs is required.")
    return args


def main(argv: list[str] | None = None) -> int:
    """Parse args, populate shared store, run flow. Returns 0 on success, non-zero on failure."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        args = parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0  # argparse error -> 2

    shared = default_shared_store()
    shared["repo_url"] = args.repo_url.strip() if args.repo_url else None
    shared["local_dir"] = args.local_dir.strip() if args.local_dir else None
    shared["project_name"] = args.project_name.strip() if args.project_name else None
    shared["output_dir"] = (args.output_dir or "output").strip()
    shared["language"] = (args.language or "english").strip()
    shared["github_token"] = os.environ.get("GITHUB_TOKEN") or shared.get("github_token")

    if getattr(args, "parent_dirs", None):
        shared["parent_dirs"] = [d.strip() for d in args.parent_dirs]
        shared["file_threshold"] = getattr(args, "file_threshold", 100)
        shared["resume"] = getattr(args, "resume", True)
        shared["parallel_workers"] = max(0, int(getattr(args, "parallel", 0) or 0))
        flow = (
            create_parallel_recursive_flow()
            if shared["parallel_workers"] > 0
            else create_recursive_flow()
        )
        source = "parent_dirs=" + ", ".join(shared["parent_dirs"])
    else:
        flow = create_full_flow()
        source = shared["local_dir"] or shared["repo_url"] or "?"

    logger.info("Starting pipeline: source=%s, language=%s", source, shared["language"])

    try:
        flow.run(shared)
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        return 1

    out_dir = shared.get("final_output_dir")
    master_index = shared.get("master_index_path")
    if master_index:
        logger.info("Master index: %s", master_index)
        print("Master index:", master_index)
    if out_dir:
        logger.info("Tutorial written to: %s", out_dir)
        print("Tutorial written to:", out_dir)
    if not out_dir and not master_index:
        logger.info("files=%s, project_name=%s", len(shared.get("files", [])), shared.get("project_name"))
        print("files count:", len(shared.get("files", [])))
        print("project_name:", shared.get("project_name"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
