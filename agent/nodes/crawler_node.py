"""!
@file crawler_node.py
@brief LangGraph node responsible for directory traversal.
@details 
This node recursively scans a specified directory and collects all file 
paths contained within it (including subdirectories). The discovered 
files are stored in a deque structure and the total count is calculated. 
The updated state is then returned to the LangGraph workflow.
"""

import os
from states.state1 import GraphState
from collections import deque

def crawl_directory(state: GraphState):
    """!
    @brief Recursively parses all files within the specified directory path.
    @details 
    Uses os.walk() to traverse the directory tree defined in the 
    GraphState's directory_path attribute. Each discovered file path 
    is appended to a deque. The function returns an updated state 
    containing:
      - files: deque of full file paths
      - total_number_of_files: total count of discovered files

    @param state GraphState
        The current state object containing at minimum:
        - directory_path (str): Path to directory being analyzed.

    @return dict
        Partial GraphState update containing:
        - files (Deque[str])
        - total_number_of_files (int)
    """
    
    files = deque()

    # recursively loop through all files in the directory path
    for root, _, filenames in os.walk(state["directory_path"]):
        for f in filenames:
            # add file to queue
            files.append(os.path.join(root, f))

    # update the GraphState
    return {
        "files": files,
        "total_number_of_files": len(files)
    }
