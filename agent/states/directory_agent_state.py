"""
@file directory_agent_state.py
@brief Defines the shared state structure used by the DirectoryAgent workflow.
"""

from typing import TypedDict, Deque, Annotated, Any
from agent.structured_output.directory_output import DirectoryOutput
from operator import add

def merge_summaries(existing: dict, new: dict) -> dict:
    """
    @brief Merges new directory summaries into the existing dict
    @param existing The existing dictionary of directory summaries
    @param new The new dictionary of directory summaries to merge in
    @return A merged dictionary containing all summaries from both existing and new, with new summaries appended
    """
    return {**existing, **new}

class DirectoryGraphState(TypedDict):
    """
    @brief Represents the shared state passed between nodes in the DirectoryAgent workflow graph.

    This state object is mutated and passed between nodes in the LangGraph workflow.
    It stores information about the codebase traversal, retrieved context, retrieval
    parameters, and resources needed by different nodes.

    @var directory_path
        The absolute path to the root directory of the codebase being analyzed.
    @var directories
        A deque of directories discovered during traversal. The crawler node populates
        this list and directories are typically processed from deepest to shallowest
        to support bottom-up summarization.
    @var code_context
        Retrieved code snippets relevant to the current directory. These are collected
        from the code vector database during retrieval and used by the summarizer.
    @var summary_context
        Retrieved file/class/function summaries relevant to the current directory.
        These come from the summary vector database and help provide higher-level
        structural context.
    @var sufficient_code_context
        Flag set by the context analyzer indicating whether enough code snippets have
        been retrieved to summarize the directory.
    @var sufficient_summary_context
        Flag set by the context analyzer indicating whether enough summary-level
        context has been retrieved.
    @var directory_summary
        The structured summary generated for the current directory by the summarizer
        node.
    @var codebase_name
        The name of the codebase being analyzed, typically derived from the root
        directory name.
    @var total_number_of_directories
        Total number of directories discovered during traversal.
    @var current_directory
        The directory currently being processed by the workflow.
    @var codebase_k
        The number of code chunks to retrieve from the code vector database during
        each retrieval iteration.
    @var file_summary_k
        The number of summary entries to retrieve from the summary vector database
        during each retrieval iteration.
    @var code_collection
        The ChromaDB collection containing embedded code snippets.
    @var summary_collection
        The ChromaDB collection containing embedded file/class/function summaries.
    """
    directory_path: str
    directories: Deque[str]
    code_context: list[str]
    summary_context: list[str]
    sufficient_code_context: bool # For the context analyser node
    sufficient_summary_context: bool # For the context analyser node
    directory_summary: DirectoryOutput
    child_summaries: Annotated[dict[str, DirectoryOutput], merge_summaries]
    codebase_name: str
    total_number_of_directories: int
    current_directory: str
    codebase_k: int
    file_summary_k: int
    code_collection: Any
    summary_collection: Any