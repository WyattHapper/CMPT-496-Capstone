"""!
@file state1.py
@brief Defines the shared state structure used by the LangGraph workflow.
@details 
This module defines the GraphState TypedDict, which represents the 
structured state passed between nodes in the LangGraph execution graph. 
Each node reads from and returns an updated version of this state.
"""

from typing import TypedDict, Deque
from agent.structured_output.summary_output import SummaryOutput

class GraphState(TypedDict):
    """!
    @brief Represents the state object shared between graph nodes.
    @details 
    This state schema defines the data tracked and modified throughout 
    the execution of the LangGraph workflow. It is used by all nodes 
    to ensure consistent data structure and type safety.

    @var directory_path
    The absolute path to the directory being analyzed.

    @var files
    A deque containing file paths discovered during directory traversal.

    @var total_number_of_files
    The total count of files discovered and stored in the files deque.
    """

    directory_path: str
    files: Deque[str] 
    file_summary: SummaryOutput
    codebase_name: str
    total_number_of_files: int
    current_file: str
