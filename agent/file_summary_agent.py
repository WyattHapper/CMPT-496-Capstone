"""
@file file_summary_agent_fast.py
@brief Defines the FileSummaryAgent, a LangGraph-based agent for generating structured summaries of source code files.
@details Implements a crawler-summarizer-writer workflow that traverses a directory, uses an LLM to produce structured file summaries, and saves the results as JSON outputs.
"""

from agent.states.file_summary_agent_state import FileGraphState
from langgraph.graph import StateGraph, START, END
from agent.structured_output.file_summary_output import FileSummaryOutput
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage
from dotenv import load_dotenv
import os
import sys
import asyncio
from pathlib import Path
from collections import deque

BATCH_SIZE = 10
MAX_CONCURRENCY = 10

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
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-3-flash-preview",
                api_key=os.getenv("GOOGLE_API_KEY"))
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

        builder = StateGraph(FileGraphState)

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
        try:
            return self.graph.invoke(initial_state)
        finally:
            self._loop.close()
            self._loop = None



    def crawler_node(self, state: FileGraphState):
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

        
    def write_file_summary_node(self, state: FileGraphState):
        base_output_dir = "./agent/file_summary_agent_output"
        codebase_subdir = os.path.join(base_output_dir, f'{state["codebase_name"]}')
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

async def _summarize_one(structured_llm, file_path: str):
    try:
        contents = Path(file_path).read_text(encoding="utf-8", errors="replace")
        messages = [
            (
                "system",
                "You analyze source code and return only structured output matching the schema."
            ),
            (
                "user",
                f"""
        Your task is to summarize the file and extract type information for UML documentation.

        Return:
        - a concise summary of the file
        - dependencies/imports
        - top-level functions
        - all types defined in the file

        Types may be:
        - class
        - enum
        - interface
        - struct

        For each type:
        - provide a short description
        - list properties or fields
        - list methods and constructors
        - list base classes in inherits_from
        - list enum values if the type is an enum
        - generate a standalone PlantUML snippet describing the type

        For properties and fields:
        - determine visibility: public, private, or protected
        - indicate whether the member is static

        For methods:
        - determine visibility
        - determine whether the method is static
        - determine whether it is a constructor
        - list parameters with direction (in, out, or inout)
        - include return type if known

        Constructor parameters must be included in the structured method entry exactly as they appear in the PlantUML signature.

        Relationship extraction:

        Two relationship types are supported:

        inheritance  
        A type inherits from another type.

        association  
        One type stores another type as a field, property, or member.

        Association rules:
        - Only create an association when a type stores another type as a field or property.
        - Do NOT create associations for:
        - local variables
        - object creation inside methods
        - parameters
        - return types
        - method calls
        - assertions
        - temporary usage inside functions
        - If a type is only used inside methods, omit the relationship.

        Method parameter consistency:
        - Every method and constructor must include its full parameter list in the structured `parameters` field.
        - The `parameters` field must match the parameters shown in the PlantUML signature.
        - Do not leave `parameters` empty for methods or constructors that take arguments.

        Test file rule:
        - In test files, do NOT create associations to types used only inside test methods.
        - Only create associations if the test class actually stores a member of that type.

        Relationship placement:
        - If both types are defined in the file, place the relationship in `relationships`.
        - If the target type is defined outside the file, place the relationship in `external_relationships`.
        - If no valid relationships exist, return empty lists.

        PlantUML rules:

        For each type:
        - the PlantUML must match the extracted structured fields exactly
        - do not include members that are missing from the structured output
        - use:
        + for public
        - for private
        # for protected
        - mark static members using `{{static}}`
        - show fields as: `+name : Type`
        - show methods as: `+method(in x : Type) : ReturnType`
        - constructors must not have return types
        
        Relationship PlantUML formatting:
        - Use `<|--` for inheritance.
        - Use `--` for association.
        - Do not use aggregation (`o--`) or composition (`*--`) symbols.

        PlantUML static member formatting:
        - For static properties and static methods, place {{static}} before the visibility symbol.
        - Correct format examples:
        {{static}} +NumericTypes : HashSet<Type>
        {{static}} +FromDictionary(in values : Dictionary<string, Dictionary<string, object>>) : ConsoleTable
        {{static}} -GetColumns<T>() : IEnumerable<string>
        - Do not place the visibility symbol before {{static}}.
        - Incorrect examples:
        +{{static}} NumericTypes : HashSet<Type>
        -{{static}} GetColumns<T>() : IEnumerable<string>

        File-level relationship diagram:

        Generate `relationship_plantuml` as a standalone diagram.

        Rules:
        - include `@startuml` and `@enduml`
        - declare all in-file types
        - include only relationships from the `relationships` field
        - do not include external relationships
        - if there are no relationships, still declare the types

        General rules:
        - only include information supported by the code
        - do not invent members or relationships
        - keep items in source order when possible

        Association filtering:
        - Prefer associations to named application, project, or file-relevant types.
        - Do not create associations to generic collection/container/helper types unless they are especially important to understanding the design.
        - Do not create associations only because a property type is a primitive, framework utility, or common container type.
        - Do not create associations to enum types.
        - Enum values may appear in properties but should not generate relationships.

        Structured data is the source of truth.
        Generate PlantUML from the structured fields, not the other way around.

        File path:
        {file_path}

        Code:
        {contents}
        """
            )
        ]
        out = await structured_llm.ainvoke(messages)
        return file_path, out, None
    except Exception as e:
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
    