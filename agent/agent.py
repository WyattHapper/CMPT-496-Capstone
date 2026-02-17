"""!
@file agent.py
@brief Entry point for executing the LangGraph workflow.
@details 
This module initializes and runs the compiled LangGraph defined in graph1.py.
It collects user input specifying which codebase to analyze, constructs the
appropriate directory path, initializes the graph state, and invokes the
graph execution. The final state output is printed to the console.
"""

from graphs.graph1 import build_graph
from collections import deque
import os


def run_agent():
    """!
    @brief Initializes and executes the LangGraph agent workflow.
    @details 
    This function:
      1. Builds the compiled LangGraph using build_graph().
      2. Determines the project root directory dynamically.
      3. Prompts the user to select a target codebase.
      4. Constructs the absolute path to the selected codebase.
      5. Initializes the GraphState with required fields.
      6. Invokes the graph and prints the resulting state.

    The function assumes that the selected codebase exists within
    the project's "targetCodebases" directory.

    @param None
    @return None
    """
    
    graph = build_graph()

    # Determine project root dynamically
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)

    # Prompt user for codebase selection
    codebase = input("Enter the codebase to analyze: ")
    directory_path = os.path.join(PROJECT_ROOT, "targetCodebases", codebase)

    # Initialize starting GraphState
    initial_state = {
        "directory_path": directory_path,
        "files": deque()
    }

    # Execute graph
    result = graph.invoke(initial_state)
    print(result)


if __name__ == "__main__":
    run_agent()
