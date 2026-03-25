"""!
@file state1.py
@brief Defines the shared state structure used by the LangGraph workflow.
@details 
This module defines the FileGraphState TypedDict, which represents the 
structured state passed between nodes in the LangGraph execution graph. 
Each node reads from and returns an updated version of this state.
"""

from typing import TypedDict, Deque, List, Dict, Annotated
from agent.structured_output.file_summary_output import FileSummaryOutput, BusinessRule

def merge_business_rules(existing: Dict[str, List[BusinessRule]], new: Dict[str, List[BusinessRule]]) -> Dict[str, List[BusinessRule]]:
    """
    @brief Merges new business rules into the existing dict, appending rather than overwriting.
    @param existing The existing dictionary of business rules keyed by file path
    @param new The new dictionary of business rules to merge in
    @return A merged dictionary with rules from both inputs
    """
    merged = {**existing}
    for key, rules in new.items():
        merged.setdefault(key, []).extend(rules)
    return merged

class FileGraphState(TypedDict):
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
    file_summaries: List[FileSummaryOutput]
    file_summary: FileSummaryOutput
    codebase_name: str
    total_number_of_files: int
    current_files: List[str]
    current_file: str
    filename_counters: Dict[str, int]
    business_rules_by_file: Annotated[Dict[str, List[BusinessRule]], merge_business_rules]
