"""
PocketFlow flow for the Code-IQ pipeline.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from pocketflow import BatchFlow, Flow

from shared_schema import default_shared_store

from nodes import (
    AnalyzeRelationships,
    CombineTutorial,
    DiscoverLeafFolders,
    FetchRepo,
    GenerateHierarchicalView,
    IdentifyAbstractions,
    OrderChapters,
    SummarizeFiles,
    UpdateJobProgress,
    WriteChapters,
)

logger = logging.getLogger("Code_IQ")

# Keys to copy from shared into each parallel run's isolated store
GLOBAL_CONFIG_KEYS = [
    "github_token",
    "include_patterns",
    "exclude_patterns",
    "max_file_size",
    "language",
]


def create_fetch_flow() -> Flow:
    """Create minimal flow with FetchRepo only (foundation)."""
    fetch_repo = FetchRepo()
    return Flow(start=fetch_repo)


def create_analysis_flow() -> Flow:
    """Create flow: FetchRepo -> IdentifyAbstractions -> AnalyzeRelationships -> OrderChapters."""
    fetch_repo = FetchRepo()
    summarize = SummarizeFiles()
    identify = IdentifyAbstractions()
    analyze = AnalyzeRelationships()
    order = OrderChapters()
    fetch_repo >> summarize >> identify >> analyze >> order
    return Flow(start=fetch_repo)


def create_full_flow() -> Flow:
    """Create full flow: FetchRepo -> IdentifyAbstractions -> AnalyzeRelationships -> OrderChapters -> WriteChapters -> CombineTutorial."""
    fetch_repo = FetchRepo()
    summarize = SummarizeFiles()
    identify = IdentifyAbstractions()
    analyze = AnalyzeRelationships()
    order = OrderChapters()
    write_chapters = WriteChapters()
    combine = CombineTutorial()
    fetch_repo >> summarize >> identify >> analyze >> order >> write_chapters >> combine
    return Flow(start=fetch_repo)


class SubfolderBatchFlow(BatchFlow):
    """Runs the inner pipeline once per leaf folder; prep returns leaf_folders, post sets completed_count."""

    def prep(self, shared):
        return shared.get("leaf_folders", [])

    def post(self, shared, prep_res, exec_res):
        shared["completed_count"] = len(prep_res or [])
        return "default"


def create_recursive_flow() -> Flow:
    """Create flow: DiscoverLeafFolders >> SubfolderBatchFlow(inner pipeline) >> GenerateHierarchicalView."""
    fetch_repo = FetchRepo()
    summarize = SummarizeFiles()
    identify = IdentifyAbstractions()
    analyze = AnalyzeRelationships()
    order = OrderChapters()
    write_chapters = WriteChapters()
    combine = CombineTutorial()
    update_progress = UpdateJobProgress()
    fetch_repo >> summarize >> identify >> analyze >> order >> write_chapters >> combine >> update_progress
    inner_flow = Flow(start=fetch_repo)
    batch = SubfolderBatchFlow(start=inner_flow)
    discover = DiscoverLeafFolders()
    hier_view = GenerateHierarchicalView()
    discover >> batch >> hier_view
    return Flow(start=discover)


class ParallelSubfolderFlow(Flow):
    """Runs the inner flow per leaf folder in a ThreadPoolExecutor with isolated shared stores."""

    def _run(self, shared):
        leaf_folders = shared.get("leaf_folders", [])
        max_workers = max(1, int(shared.get("parallel_workers") or 3))
        inner_flow = self.start_node
        global_cfg = {k: shared[k] for k in GLOBAL_CONFIG_KEYS if k in shared}
        job_id = shared.get("job_id")
        total = len(leaf_folders)
        completed_count = [0]  # use list to allow closure to mutate

        def run_one(bp):
            iso = default_shared_store()
            iso.update(global_cfg)
            iso.update(bp)
            inner_flow._orch(iso, {**self.params, **bp})
            return iso.get("final_output_dir"), bp.get("project_name", "")

        completed = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(run_one, bp): bp for bp in leaf_folders}
            for fut in as_completed(futures):
                try:
                    out, project_name = fut.result()
                    if out:
                        completed.append(out)
                    if job_id and total:
                        completed_count[0] += 1
                        try:
                            from api import job_store
                            job_store.update_progress(job_id, completed_count[0], total, project_name or "")
                        except Exception as e:
                            logger.warning("Progress update failed: %s", e)
                except Exception as e:
                    logger.warning("Folder failed: %s", e)
        shared["completed_folders"] = completed
        shared["completed_count"] = len(completed)
        return "default"


def create_parallel_recursive_flow() -> Flow:
    """Create flow: DiscoverLeafFolders >> ParallelSubfolderFlow(inner pipeline) >> GenerateHierarchicalView."""
    fetch_repo = FetchRepo()
    summarize = SummarizeFiles()
    identify = IdentifyAbstractions()
    analyze = AnalyzeRelationships()
    order = OrderChapters()
    write_chapters = WriteChapters()
    combine = CombineTutorial()
    fetch_repo >> summarize >> identify >> analyze >> order >> write_chapters >> combine
    inner_flow = Flow(start=fetch_repo)
    parallel_batch = ParallelSubfolderFlow(start=inner_flow)
    discover = DiscoverLeafFolders()
    hier_view = GenerateHierarchicalView()
    discover >> parallel_batch >> hier_view
    return Flow(start=discover)
