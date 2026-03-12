"""
@file file_summary_agent_fast.py
@brief Defines the FileSummaryAgent, a LangGraph-based agent for generating structured summaries of source code files.
@details Implements a crawler-summarizer-writer workflow that traverses a directory, uses an LLM to produce structured file summaries, and saves the results as JSON outputs.
"""

from agent.states.file_summary_agent_state import GraphState
from langgraph.graph import StateGraph, START, END
from agent.structured_output.file_summary_output import FileSummaryOutput
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from dotenv import load_dotenv
import os
import sys
import random
import asyncio
from pathlib import Path
from collections import deque

BATCH_SIZE = 4
MAX_CONCURRENCY = 2

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
    def __init__(self, llm = None):
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
        if llm is not None:
            self.llm = llm
            self.structured_llm = self.llm.with_structured_output(FileSummaryOutput)
            self.graph = self.build_graph()
        else:
            load_dotenv()
            self.llm = ChatOpenAI(
                model="gpt-4.1",
                api_key=os.getenv("OPENAI_API_KEY"),  # or omit and rely on env var
                temperature=0,                        # helps structured output stability
            )
            self.structured_llm = self.llm.with_structured_output(FileSummaryOutput)
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
            "files": deque(),
            "filename_counters": {},
            "file_summaries": [],
            "current_files": []
        }

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            return self.graph.invoke(initial_state)
        finally:
            self._loop.close()
            asyncio.set_event_loop(None)
            self._loop = None



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
            filenames.sort()
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
    
    def summarizer_node(self, state):
        # pop a batch
        batch = []
        while state["files"] and len(batch) < BATCH_SIZE:
            batch.append(state["files"].popleft())

        async def run_batch():
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            async def guarded(fp):
                async with sem:
                    return await _summarize_one(self.structured_llm, fp)
            return await asyncio.gather(*(guarded(fp) for fp in batch))

        results = self._loop.run_until_complete(run_batch())

        summaries = []
        for file_path, output, err in results:
            if err is not None:
                summaries.append(FileSummaryOutput(path=file_path, summary=f"Error generating summary: {err}"))
            elif isinstance(output, FileSummaryOutput):
                summaries.append(output)
            elif isinstance(output, AIMessage):
                summaries.append(FileSummaryOutput(path=file_path, summary=output.content))
            else:
                summaries.append(FileSummaryOutput(path=file_path, summary=str(output)))

        return {
            "file_summaries": summaries,
            "current_files": [Path(p).name for p in batch],
        }

        
    def write_file_summary_node(self, state: GraphState):
        base_output_dir = "./agent/file_summary_agent_output"
        codebase_subdir = os.path.join(base_output_dir, f"{state['codebase_name']}_gpt")
        os.makedirs(codebase_subdir, exist_ok=True)

        counters = state["filename_counters"]

        for summary in state["file_summaries"]:
            source_path = summary.path
            base = os.path.basename(source_path)          # config.py
            stem = base.replace(".", "-")                  # config-py

            # increment counter
            count = counters.get(stem, 0) + 1
            counters[stem] = count

            safe_name = f"{stem}__{count}.json"
            full_path = os.path.join(codebase_subdir, safe_name)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(summary.model_dump_json(indent=2))

        return state

async def _summarize_one(structured_llm, file_path: str, max_retries: int = 6):
    contents = Path(file_path).read_text(encoding="utf-8", errors="replace")
    messages = [
        ("system", "You are a helpful assistant that creates concise, accurate summaries of code files."),
        ("user", f"File path: {file_path}\nSummarize the following code file:\n{contents}")
    ]

    for attempt in range(max_retries):
        try:
            out = await structured_llm.ainvoke(messages)

            if isinstance(out, FileSummaryOutput):
                return file_path, out, None

            parsed = getattr(out, "parsed", None)
            if isinstance(parsed, FileSummaryOutput):
                return file_path, parsed, None

            return file_path, FileSummaryOutput(path=file_path, summary=str(out)), None

        except Exception as e:
            msg = str(e).lower()
            is_rl = ("rate limit" in msg) or ("429" in msg)

            if is_rl and attempt < max_retries - 1:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"⏳ rate limited: {file_path} — retrying in {wait:.1f}s ({attempt+1}/{max_retries})")
                await asyncio.sleep(wait)
                continue

            return file_path, None, e
        finally:
            print(f"✔ finished: {file_path}")

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
    