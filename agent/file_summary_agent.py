"""
@file file_summary_agent.py
@brief Defines the FileSummaryAgent, a LangGraph-based agent for generating structured summaries of source code files.
@details Implements a crawler-summarizer-writer workflow that traverses a directory, uses an LLM to produce structured file summaries, and saves the results as JSON outputs.
"""

from agent.states.file_summary_agent_state import GraphState
from langgraph.graph import StateGraph, START, END
from agent.structured_output.summary_output import SummaryOutput
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from collections import deque

class FileSummaryAgent:
    """
    @brief LangGraph-based agent for generating structured summaries of source code files.

    @details
    The FileSummaryAgent constructs and executes a LangGraph workflow that:
    - Crawls a directory to discover source code files.
    - Uses a large language model to generate structured summaries.
    - Outputs summaries in JSON format.

    The agent internally manages:
    - The language model configuration
    - Structured output formatting
    - Graph construction and execution

    The directory to analyze is provided when calling the run() method.
    """
    def __init__(self):
        """
        @brief Initializes the FileSummaryAgent.

        @details
        This constructor:
        - Loads environment variables.
        - Configures the language model.
        - Enables structured output using SummaryOutput.
        - Builds and compiles the LangGraph workflow.

        @return None
        """

        load_dotenv()
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=os.getenv("GOOGLE_API_KEY"))
        self.structured_llm = self.llm.with_structured_output(SummaryOutput)
        self.graph = self.build_graph()


    def build_graph(self):
        """
        @brief Builds and compiles the LangGraph workflow.

        @details
        Creates a state graph with three nodes:
        - crawler: collects files to summarize
        - summarizer: generates summaries using the LLM
        - writer: saves summaries to disk

        Execution starts at the crawler node and proceeds sequentially.
        The workflow repeats summarization until no files remain.

        @return Compiled execution graph.
        """

        builder = StateGraph(GraphState)

        # define nodes
        builder.add_node("crawler", self.crawler_node)
        builder.add_node("summarizer", self.summarizer_node)
        builder.add_node("writer", self.write_file_summary_node)

        # set path
        builder.set_entry_point("crawler")  # start
        builder.add_edge("crawler", "summarizer")
        builder.add_edge("summarizer", "writer")
        builder.add_conditional_edges("writer", lambda state: "summarizer" if state["files"] else END,) # conditional end
        
        return builder.compile()
    
    def run(self, directory_path):
        """
        @brief Executes the FileSummaryAgent workflow on a given directory.

        @details
        Initializes the starting state with the target directory, then
        runs the compiled LangGraph to crawl files, generate summaries,
        and write output to disk.

        @param directory_path str: Absolute path to the codebase to analyze.
        @return dict: Final state of the graph after execution.
        """

        # Initialize starting GraphState
        initial_state = {
            "directory_path": directory_path,
            "files": deque()
        }

        # return the executed version of graph
        return self.graph.invoke(initial_state)



    def crawler_node(self, state: GraphState):
        """
        @brief Recursively collects all code files from the target directory.

        @details
        Traverses the directory tree defined in `state["directory_path"]`,
        filtering for common code file extensions. Populates a deque of file
        paths and returns the total number of discovered files.

        @param state GraphState: Current graph state containing at least:
            - directory_path (str): Path of the directory to scan.
        
        @return dict: Updated state containing:
            - files (Deque[str]): Queue of discovered file paths.
            - total_number_of_files (int): Count of files found.
        """
        
        files = deque()
        acceptable_extensions = [".cs", ".py", ".md", ".js", ".ts", ".sh", ".bash", ".c", ".cpp", ".html", ".css", ".yml", ".yaml"]

        codebase_name = Path(state["directory_path"]).name

        # recursively loop through all files in the directory path
        for root, _, filenames in os.walk(state["directory_path"]):
            for f in filenames:
                file_ext = Path(f).suffix.lower()
                if file_ext in acceptable_extensions:
                    # add file to queue
                    files.append(os.path.join(root, f))

        # update the GraphState
        return {
            "files": files,
            "total_number_of_files": len(files),
            "codebase_name": codebase_name
        }
    
    def summarizer_node(self, state: GraphState):
        """
        @brief Node which calls the LLM to generate a summary for a single file
        @details Pops a file from the stack, reads its contents, and prompts the LLM to generate a summary. Should loop back to this
        node until the stack is empty
        @param state The current state of the graph
        """

        file = state['files'].pop()
        with open(file, 'r') as f:
            contents = f.read()
        
        messages = [
            ("system", "You are a helpful assistant that creates concise, accurate summaries of code files."),
            ("user", f"""
                File path: {file}
                Summarize the following code file: {contents}
            """)
        ]

        output =  self.structured_llm.invoke(messages)

        # visual to see if program gets frozen or actually progresses through the codebase
        print("Finished:", file)
        
        return {
           "file_summary": output, 
           "current_file": Path(file).name
        }
        
    def write_file_summary_node(self, state: GraphState):
        """
        @brief Writes a file summary to disk as a JSON file.

        @details
        Creates the output directory if it does not exist, then writes the
        structured summary stored in `state["file_summary"]` to a JSON file.
        The output file name is derived from `state["current_file"]` with
        periods replaced by hyphens.

        @param state GraphState: Current graph state containing:
            - file_summary (SummaryOutput): Structured LLM summary.
            - current_file (str): Name of the summarized file.

        @return GraphState: Unmodified state passed to the next node.
        """

        base_output_dir = "./agent/file_summary_agent_output"
        
        # 2. Append the codebase name to create a subdirectory
        # state["codebase_name"] comes from the crawler node
        codebase_subdir = os.path.join(base_output_dir, state["codebase_name"])
        
        os.makedirs(codebase_subdir, exist_ok=True)

        summary_file = state['file_summary']
        file_name = str(state['current_file'])
        
        # 3. Create the full file path inside the subdirectory
        # We still replace dots with hyphens to avoid double-extension confusion
        safe_name = file_name.replace(".", "-") + ".json"
        full_path = os.path.join(codebase_subdir, safe_name)

        with open(full_path, "w") as f:
            f.write(summary_file.model_dump_json(indent=2))
            
        return state


if __name__ == "__main__":
    """
    @brief Script entry point for running FileSummaryAgent.

    @details
    Prompts the user for a target codebase, builds the directory path,
    runs the agent, and prints a completion message.

    @return None
    """

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)

    if len(sys.argv) != 2:
        print("Usage: python file_summary_agent.py <codebase_name>")
        sys.exit(1)
    codebase = sys.argv[1]
    directory_path = os.path.abspath(codebase)

    agent = FileSummaryAgent()
    agent.run(directory_path)
    print("FileSummaryAgent has completed it's task!")
    