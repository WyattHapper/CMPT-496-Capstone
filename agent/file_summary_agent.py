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
import json
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
        builder.add_node("business_rules_writer", self.write_business_rules_node)

        # set path
        builder.set_entry_point("crawler")  # start
        builder.add_edge("crawler", "summarizer")
        builder.add_edge("summarizer", "writer")
        builder.add_conditional_edges(
            "writer",
            lambda state: "summarizer" if state["files"] else "business_rules_writer",
        )
        builder.add_edge("business_rules_writer", END)
        
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
            "current_files": [],
            "business_rules_by_file": {}
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
        acceptable_extensions = [".cs", ".py", ".md", ".js", ".ts", ".sh", ".bash", ".c", ".cpp", ".html", ".css"]

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

        batch_rules = {}
        for summary in summaries:
            if summary.business_rules:
                batch_rules[summary.path] = summary.business_rules

        return {
            "file_summaries": summaries,
            "current_files": [Path(p).name for p in batch],
            "business_rules_by_file": batch_rules,
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

        return {"filename_counters": counters}

    def write_business_rules_node(self, state: FileGraphState):
        """
        @brief Writes the aggregated business rules to a JSON file.

        @details
        Serializes the business_rules_by_file dict and writes it to a
        dedicated subdirectory under the codebase output folder.

        @param state FileGraphState: Current graph state.
        @return dict: Unchanged state.
        """
        base_output_dir = "./agent/file_summary_agent_output"
        br_dir = os.path.join(base_output_dir, state["codebase_name"], "business_rules")
        os.makedirs(br_dir, exist_ok=True)

        output_path = os.path.join(br_dir, "business_rules.json")

        serializable = {
            path: [rule.model_dump() for rule in rules]
            for path, rules in state["business_rules_by_file"].items()
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)

        return {}

async def _summarize_one(structured_llm, file_path: str):
    try:
        contents = Path(file_path).read_text(encoding="utf-8", errors="replace")
        messages = [
            (
                "system",
                "You are a senior software architect. Analyze source code and return only structured output matching the schema."
            ),
            (
                "user",
                f"""### Tasks
Analyze the file and produce:
1. A concise summary, dependencies, top-level functions, and all type definitions
2. UML-ready structured data and PlantUML diagrams
3. Business rules evidenced by the code

### Type extraction
Types may be: class, enum, interface, or struct.

For each type:
- provide a short description
- list properties/fields with visibility (public, private, protected) and whether static
- list methods/constructors with visibility, static flag, parameters (with direction: in, out, inout), and return type
- list base classes in inherits_from
- list enum values if applicable
- generate a standalone PlantUML snippet describing the type

Constructor parameters must appear in the structured method entry exactly as in the PlantUML signature. Every method and constructor must include its full parameter list in the `parameters` field.

### Relationship extraction
Two relationship types are supported: inheritance and association.

Association rules:
- Only create an association when a type stores another type as a field or property.
- Do NOT create associations for local variables, parameters, return types, method calls, object creation inside methods, assertions, or temporary usage.
- In test files, only create associations if the test class stores a member of that type.

Relationship placement:
- Both types in this file: place in `relationships`.
- Target type outside this file: place in `external_relationships`.
- No valid relationships: return empty lists.

Association filtering:
- Prefer associations to named application/project types.
- Do not create associations to generic containers, primitives, framework utilities, or enum types.

### PlantUML rules
For each type, the PlantUML must match the structured fields exactly.
- `+` public, `-` private, `#` protected
- Fields: `+name : Type`
- Methods: `+method(in x : Type) : ReturnType`
- Constructors: no return type
- Static members: place `{{static}}` before the visibility symbol
  Correct: `{{static}} +Name : Type`
  Incorrect: `+{{static}} Name : Type`
- Inheritance: `<|--`
- Association: `--`
- Do not use `o--` or `*--`

### File-level relationship diagram
Generate `relationship_plantuml` as a standalone diagram with `@startuml`/`@enduml`.
- Declare all in-file types
- Include only `relationships` (not external)
- If no relationships exist, still declare the types

### Business rule extraction
Extract business rules that are **directly evidenced** by code in this file.

A business rule is a constraint, policy, threshold, validation, access control check, or behavioral requirement **that governs how the software product behaves for its users or within its problem domain**.

**Do NOT extract** operational, infrastructure, or DevOps rules such as:
- CI/CD pipeline configuration (branch triggers, build matrix, deployment gates)
- Build system settings (SDK versions, build configurations, restore steps)
- Package publishing or release policies (NuGet, npm, PyPI publishing rules)
- Repository or version control policies (branch protection, PR rules, line ending settings)
- Environment setup or toolchain configuration

These are development-process rules, not product business rules. If a file contains only infrastructure or DevOps configuration (e.g., CI/CD YAML, build scripts, deployment manifests), return an empty business rules list.

Rules:
- Only extract rules supported by code you can see. Do not speculate about cross-file behavior.
- For each rule, provide a concise statement of the business rule
- If no business rules are evident, return an empty list.

Positive example — extract rules like these:
Given this code:
```csharp
if (order.Total < 0)
    throw new ArgumentException("Order total cannot be negative");
if (order.Items.Count == 0)
    throw new InvalidOperationException("Cannot process empty order");
```

Return:
- rule: "Order total must be non-negative"
- rule: "An order must contain at least one item to be processed"

Negative example — do NOT extract rules like these:
Given this CI/CD configuration:
```yaml
branches:
  only:
    - master
deploy:
  on:
    branch: master
    appveyor_repo_tag: true
nuget:
  disable_publish_on_pr: true
```
These describe CI/CD pipeline behavior and deployment policies, not product domain logic. Return an empty business rules list for files like this.

### General rules
- Only include information supported by the code
- Do not invent members, relationships, or business rules
- Keep items in source order when possible
- Structured data is the source of truth. Generate PlantUML from the structured fields, not the other way around.

File path:
{file_path}

Code:
{contents}
"""
            )
        ]
        out = await structured_llm.ainvoke(messages)
        if isinstance(out, FileSummaryOutput):
            for rule in out.business_rules:
                rule.source_file = file_path
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
    