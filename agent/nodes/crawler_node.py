import os
from states.state1 import GraphState
from collections import deque

def crawl_directory(state: GraphState):
    files = deque()

    for root, _, filenames in os.walk(state["directory_path"]):
        for f in filenames:
            files.append(os.path.join(root, f))

    return {
        "files": files,
        "total_number_of_files": len(files)
    }
