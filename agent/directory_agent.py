from agent.states.directory_agent_state import DirectoryGraphState
from agent.structured_output.directory_output import DirectoryOutput
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
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
            "code_context": [],
            "summary_context": [],
            "sufficient_context_retrieved": False,
            "codebase_k": 3,
            "file_summary_k": 3,
            "child_summaries": {}
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

        first_dir = discovered_directories.pop()

        return {
            "directories": deque(discovered_directories),
            "total_number_of_directories": len(discovered_directories),
            "codebase_name": Path(root_path).name,
            "current_directory": first_dir
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
        @brief Generates a summary of the current directory based on retrieved context and updates the state with the summary.
        @param state Workflow state object containing the current directory and retrieved context.
        @return Updated state with directory summary in the form of a DirectoryOutput object.
        """
        if (isinstance(self.llm, GenericFakeChatModel)):
            output = self.llm.invoke("")
            return DirectoryOutput(
                directory_name = Path(state["current_directory"]).name,
                directory_path = state["current_directory"],
                purpose = output.content
            )
        
        try:
            # Structure LLM output
            strucured_llm = self.llm.with_structured_output(DirectoryOutput)

            # Gather all relevant context for summarization
            current_dir = state["current_directory"]
            child_summaries = self._get_child_directory_summaries(current_dir, state["child_summaries"])
            formatted_child_summaries = self._format_child_summaries(child_summaries)
            summary_context = "\n\n".join(state["summary_context"])
            code_context = "\n\n".join(state["code_context"])

            # Create prompt and system message for LLM
            system_message = "You are a Senior Software Architect. Your task is to provide a high-level technical summary of a specific directory in a large codebase."
            prompt = f"""DIRECTORY TO ANALYZE: {state['current_directory']}

                        INPUT DATA:
                        1. CHILD DIRECTORY SUMMARIES:
                        {formatted_child_summaries}

                        2. FILE-LEVEL SUMMARIES:
                        {summary_context}

                        3. CODE SNIPPETS:
                        {code_context}

                        INSTRUCTIONS:
                        Follow these steps to generate your summary:
                        1. Identify the main purpose of this directory and its contents, based on the input data provided. Consider the summaries of child directories, file-level summaries, and any relevant code snippets to inform your understanding.
                        2. Identify any smaller responsibilities that this directory handles.

                        Create your output based on the structured output format provided. For the purpose, favour completeness over conciseness, but avoid including unnecessary details.

                        Example:
                        directory_name: "Benchmarks"
                        directory_path: "targetCodebases/Humanizer/src/Benchmarks"
                        purpose: "This directory contains benchmarking scripts and related resources for evaluating the performance of the codebase. The scripts here are designed to run various performance tests and generate reports based on the results."
                        responsibilities: ["Performance Testing", "Benchmarking Scripts"]
                        """
            messages = [("system", system_message), ("user", prompt)]

            # Generate summary using LLM
            output = strucured_llm.invoke(messages)

            print(f"Generated summary for directory {state['current_directory']}")

            # Update deque of directories, current_dir

            return {
                "code_context": [], # Clear code and summary context and k after summarization so that the next retrieval starts fresh
                "summary_context": [],
                "codebase_k": 10,
                "file_summary_k": 10,
                "directory_summary": output,
            }
        except Exception as e:
            print(f"Error during summarization: {e}")
            raise e



    def writer_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        state["directories"].pop()

    def _get_child_directory_summaries(self, current_dir: str, summaries_dict: dict[str, DirectoryOutput]) -> list[DirectoryOutput]:
        """
        @brief Retrieves summaries of all child directories of the current directory.
        @param current_dir The path of the current directory being processed.
        @param summaries_dict Dictionary mapping directory paths to their DirectoryOutput summaries.
        @return List of DirectoryOutput objects for child directories.
        """
        child_summaries = []
        
        # Find all entries in summaries_dict whose parent is current_dir
        for dir_path, summary in summaries_dict.items():
            # Check if dir_path is a direct child of current_dir
            if os.path.dirname(dir_path) == current_dir:
                child_summaries.append(summary)
        
        return child_summaries

    def _format_child_summaries(self, summaries: list[DirectoryOutput]) -> str:
        """
        @brief Formats child directory summaries into a readable string for the LLM prompt.
        @param summaries List of DirectoryOutput objects for child directories.
        @return Formatted string representation of child summaries.
        """
        if not summaries:
            return "No child directories found or summarized yet."
        
        formatted = []
        for summary in summaries:
            text = f"""Directory: {summary.directory_name}
                    Path: {summary.directory_path}
                    Purpose: {summary.purpose}
                    Responsibilities: {', '.join(summary.responsibilities) if summary.responsibilities else 'None identified'}"""
            formatted.append(text)
        
        return "\n\n".join(formatted)

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
    