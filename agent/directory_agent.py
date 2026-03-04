from agent.states.directory_agent_state import DirectoryGraphState
from agent.structured_output.directory_output import DirectoryOutput
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from collections import deque

class DirectoryAgent:
    def __init__(self, model = None):
        """
        @brief Initializes the DirectoryAgent with a specified language model. If no model is provided, it defaults to "gemini-3-flash-preview".
        @param model An optional language model to use for generating summaries
        """
        if model is None:
            load_dotenv()
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set.")
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-3-flash-preview",
                api_key=api_key)
        else:
            self.llm = model
        self.graph = self.build_graph()

    def build_graph(self) -> StateGraph[DirectoryGraphState]:
        """
        @brief Constructs the StateGraph that defines the workflow of the DirectoryAgent.
        @return A StateGraph object representing the workflow of the DirectoryAgent.
        """
        builder = StateGraph(DirectoryGraphState)

        # Set nodes
        builder.add_node("crawler", self.crawler_node)
        builder.add_node("retriever", self.retriever_node)
        builder.add_node("context_analyser", self.context_analyser_node)
        builder.add_node("summarizer", self.summarizer_node)
        builder.add_node("writer", self.writer_node)

        # Set edges
        builder.set_entry_point("crawler")
        builder.add_edge("crawler", "retriever")
        builder.add_edge("retriever", "context_analyser")
        builder.add_conditional_edges("context_analyser", lambda state: "summarizer" if state["sufficient_context_retrieved"] else "retriever")
        builder.add_edge("summarizer", "writer")
        builder.add_conditional_edges("writer", lambda state: "retriever" if state["directories"] else "END")

        return builder.compile()
    
    def run(self, directory_path: str):
        """
        @brief Executes the DirectoryAgent workflow starting from the provided initial state.
        @param directory_path The path to the directory to be analyzed.
        """
        initial_state = {
            "directory_path": directory_path,
            "directories": deque()
        }

        return self.graph.invoke(initial_state)

    def crawler_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        pass

    def retriever_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        pass

    def context_analyser_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        pass

    def summarizer_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        pass

    def writer_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        pass