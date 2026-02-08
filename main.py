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
from flow import create_full_flow

logger = logging.getLogger("codebase_knowledge_builder")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. Requires one of --repo-url or --local-dir."""
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
    if not args.repo_url and not args.local_dir:
        p.error("One of --repo-url or --local-dir is required.")
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

    source = shared["local_dir"] or shared["repo_url"] or "?"
    logger.info("Starting pipeline: source=%s, language=%s", source, shared["language"])

    try:
        flow = create_full_flow()
        flow.run(shared)
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        return 1

    out_dir = shared.get("final_output_dir")
    if out_dir:
        logger.info("Tutorial written to: %s", out_dir)
        print("Tutorial written to:", out_dir)
    else:
        logger.info("files=%s, project_name=%s", len(shared.get("files", [])), shared.get("project_name"))
        print("files count:", len(shared.get("files", [])))
        print("project_name:", shared.get("project_name"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
