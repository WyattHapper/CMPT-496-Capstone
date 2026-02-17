from graphs.graph1 import build_graph
from collections import deque
import os

def run_agent():
    graph = build_graph()

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    codebase = input("Enter the codebase to analyze: ")
    # might need to have team meeting to make sure we all have same subdirectory name for codebases
    directory_path = os.path.join(PROJECT_ROOT, "targetCodebases", codebase) 

    initial_state = {
        "directory_path": directory_path,  
        "files": deque()
    }

    result = graph.invoke(initial_state)
    print(result)

if __name__ == "__main__":
    run_agent()
