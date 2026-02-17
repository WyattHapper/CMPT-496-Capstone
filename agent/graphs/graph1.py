"""!
@file graph1.py
@brief Defines and compiles the LangGraph execution graph.
@details 
This module constructs the LangGraph workflow by defining its nodes,
entry point, and execution flow. The compiled graph is returned to be
invoked by agent.py during runtime.
"""

from langgraph.graph import StateGraph
from states.state1 import GraphState
from nodes.crawler_node import crawl_directory

def build_graph():
    """!
    @brief Builds and compiles the LangGraph state machine.
    @details 
    Creates a StateGraph using the defined GraphState schema. 
    Registers the crawler node, sets it as the entry point of the graph,
    and defines the execution flow to terminate after the crawler completes.

    @param None
    @return CompiledStateGraph The compiled LangGraph object ready for execution.
    """
    
    builder = StateGraph(GraphState)

    builder.add_node("crawler", crawl_directory)
    # sets starting point of graph to crawler_node.py 
    builder.set_entry_point("crawler")
    builder.add_edge("crawler", "__end__")

    return builder.compile()
