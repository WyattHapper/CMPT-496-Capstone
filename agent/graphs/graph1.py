from langgraph.graph import StateGraph
from states.state1 import GraphState
from nodes.crawler_node import crawl_directory

def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("crawler", crawl_directory)
    builder.set_entry_point("crawler")
    builder.add_edge("crawler", "__end__")

    return builder.compile()
