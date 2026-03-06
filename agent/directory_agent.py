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
        builder.add_conditional_edges("writer", lambda state: "retriever" if state["directories"] else END)

        return builder.compile()
    
    def run(self, directory_path: str):
        """
        @brief Executes the DirectoryAgent workflow starting from the provided initial state.
        @param directory_path The path to the directory to be analyzed.
        """
        initial_state = {
            "directory_path": directory_path,
            "directories": deque(),
            "retrieved_context": [],
            "sufficient_context_retrieved": False,
            "codebase_k": 3,
            "file_summary_k": 3
        }

        return self.graph.invoke(initial_state)

    def crawler_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        @brief Recursively collects subdirectories of a given directory, ignoring system/irrelevant folders.
        @param state Workflow state containing "directory_path" as the root to crawl.
        @return Updated state with:
            - "directories": deque of discovered subdirectory paths, deepest first
            - "total_number_of_directories": count of discovered directories
            - "codebase_name": name of the root directory
        @raises ValueError if "directory_path" is not a valid directory.
        """
        root_path = state["directory_path"]

        # error check path
        if not os.path.isdir(root_path):
            raise ValueError(f"Invalid directory path: {root_path}")

        discovered_directories = []
        IGNORED_DIRS = {
            ".git",
            ".github",
            "__pycache__",
            "node_modules",
            "bin",
            "obj",
            ".venv",
            ".vscode",
            "NuSpecs", 
            "NuSpec",
            "Debug"
        } # may have to be changed depending on what we deem useful

        # Walk directory tree
        for root, dirs, _ in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]  # removes directories that are in IGNORED_DIRS
            for d in dirs:
                full_path = os.path.join(root, d)
                discovered_directories.append(full_path)

        # Sort deepest directories first (bottom-up summarization)
        discovered_directories.sort(
            key=lambda path: path.count(os.sep),
            reverse=True
        )

        return {
            "directories": deque(discovered_directories),
            "total_number_of_directories": len(discovered_directories),
            "codebase_name": Path(root_path).name,
        }        

    def retriever_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        A note to whoever builds this node: The retrieved_context field in the graph state is set to append instead of overwrite by default. Therefore,
        if the next node loops back to this one to have it retrieve additional context, you can just write to that state field normally and it will append.
        The summarizer node should manually clear this field when the summary is generated so that the next retrieval step starts fresh. It is also worth noting
        that if the retriever node is looped back to to gather additional context, it should gather different context than the previous time. One idea to do so 
        would be to track a number k, which would be the amount of results to be retrieved (top-k results). The context analyser could then increment this number if 
        it determines that more context is needed, and the retriever node would retrieve the top-k results according to that number. k should then be added to the
        graph state, and it should also be noted that this process would need to be done for both of the vector stores (code and summary)
        """
        pass

    def context_analyser_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        A note to whoever builds this node: I (Nico) added a bool to the state object called "sufficient_context_retrieved". This bool is checked in a
        conditional edge in the graph after this node, to determine if it should loop back to the retriever.
        """
        pass

    def summarizer_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        A note to whoever builds this node: Because the GenericFakeChatModel used for testing cannot use structured output, you will have to check
        if that model is being used here, and if so, you will have to manually create and return the structured output object.
        Also, as mentioned in the context analyser node, make sure to clear the retrieved_context field and reset the sufficient_context_retrieved flag
        in the state object in this node, so that the next retrieval step starts with an empty context.
        """
        pass

    def writer_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        state["directories"].pop()

if __name__ == "__main__":
    """
    @brief Script entry point for running directory_agent.

    @details

    @return None
    """

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)

    if len(sys.argv) != 2:
        print("Usage: python file_summary_agent.py <codebase_name>")
        sys.exit(1)
    codebase = sys.argv[1]
    directory_path = os.path.abspath(codebase)

    agent = DirectoryAgent()
    agent.run(directory_path)
    print("DirectoryAgent has completed it's task!")
    