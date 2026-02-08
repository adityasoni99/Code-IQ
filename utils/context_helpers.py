"""
Helpers for formatting file list and content for LLM prompts.

Used by IdentifyAbstractions, AnalyzeRelationships, and other nodes that need
index # path listings and content snippets.
"""


def create_llm_context(files: list[tuple[str, str]]) -> tuple[str, list[tuple[int, str]]]:
    """
    Format the file list with indices for LLM prompts.

    Args:
        files: List of (path, content) tuples (e.g. shared["files"]).

    Returns:
        A tuple of (context_string, file_info) where context_string contains
        file content with indices and file_info is a list of (index, path) tuples.
    """
    context = ""
    file_info = []  # Store tuples of (index, path)
    for i, (path, content) in enumerate(files):
        entry = f"--- File Index {i}: {path} ---\n{content}\n\n"
        context += entry
        file_info.append((i, path))

    return context, file_info  # file_info is list of (index, path)


def get_content_for_indices(
    files: list[tuple[str, str]],
    indices: list[int],
) -> dict[str, str]:
    """
    Return content for the given file indices, formatted for LLM prompts.

    Args:
        files: List of (path, content) tuples (e.g. shared["files"]).
        indices: List of file indices to include.

    Returns:
        A dictionary mapping "index # path" strings to file content.
        Invalid indices are skipped.
    """
    content_map = {}
    for i in indices:
        if 0 <= i < len(files):
            path, content = files[i]
            content_map[f"{i} # {path}"] = (
                content  # Use index + path as key for context
            )
    return content_map
