"""
PocketFlow flow for the Code-IQ pipeline.
"""

from pocketflow import Flow

from nodes import (
    AnalyzeRelationships,
    CombineTutorial,
    FetchRepo,
    IdentifyAbstractions,
    OrderChapters,
    SummarizeFiles,
    WriteChapters,
)


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
