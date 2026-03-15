from agent.states.directory_agent_state import DirectoryGraphState
from agent.structured_output.directory_output import DirectoryOutput, ContextAnalysisOutput
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from openai import RateLimitError
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from dotenv import load_dotenv
import time
import os
import sys
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
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
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set.")
            self.llm = ChatOpenAI(
                model="gpt-4.1",
                api_key=api_key,
                temperature=0)
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
        builder.add_conditional_edges(
            "context_analyser",
            lambda state: "summarizer"
            if state["sufficient_code_context"] and state["sufficient_summary_context"]
            else "retriever"
        )
        builder.add_edge("summarizer", "writer")
        builder.add_conditional_edges(
            "writer",
            lambda state: "retriever" if state["current_directory"] else END
        )

        return builder.compile()
    
    def run(self, directory_path: str):
        """
        @brief Executes the DirectoryAgent workflow starting from the provided initial state.
        @param directory_path The path to the directory to be analyzed.
        """
        codebase_name = Path(directory_path).name

        script_dir = Path(__file__).parent.resolve()
        db_dir = (script_dir.parent / "vectorStores").resolve()

        embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        client = chromadb.PersistentClient(path=str(db_dir))

        code_collection = client.get_collection(
            name=f"{codebase_name}_code_db",
            embedding_function=embedding_fn
        )

        summary_collection = client.get_collection(
            name=f"{codebase_name}_summary_db",
            embedding_function=embedding_fn
        )

        initial_state = {
            "directory_path": directory_path,
            "directories": deque(),
            "code_context": [],
            "summary_context": [],
            "sufficient_code_context": False,
            "sufficient_summary_context": False,
            "codebase_k": 10,
            "file_summary_k": 10,
            "current_directory": "",
            "codebase_name": codebase_name,
            "total_number_of_directories": 0,
            "child_summaries": {},
            "code_collection": code_collection,
            "summary_collection": summary_collection
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

        discovered_directories = [root_path]
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
        @brief Retrieves relevant code and summary context for the current directory using vector search.
            This node performs retrieval as part of the agentic RAG loop. It queries two ChromaDB
            vector collections:
                - A code collection containing embedded code snippets.
                - A summary collection containing embedded file/class/function summaries.

            Retrieval is based on a query constructed from the current directory's relative path
            and name. Results are prioritized so that entries belonging to the current directory
            appear before context from other directories.

            The retrieved context is appended to the existing state context. This allows multiple
            retrieval iterations to accumulate additional information if the context analyzer
            determines that more context is required.

            Retrieval depth is controlled by the following parameters stored in the state:
                - codebase_k: number of code snippets to retrieve.
                - file_summary_k: number of summary entries to retrieve.

            These values may be increased by the context analyzer node during subsequent iterations.
        @param state
            The current workflow state containing directory traversal information, retrieval
            parameters, and vector store handles.
        @return DirectoryGraphState
            Updated state containing:
                - current_directory: the directory currently being processed
                - code_context: updated list of retrieved code snippets
                - summary_context: updated list of retrieved summaries
        @throws ValueError
            If no directories remain to retrieve context for.
        @note
            Retrieval prioritizes context originating from the current directory, but may also
            include related context from other directories to provide broader architectural
            information.
        @note
            Context lists accumulate across retrieval iterations. The summarizer node is
            responsible for clearing these lists when a directory summary has been generated,
            ensuring that the next directory begins with a fresh retrieval context.
        """
        # get current directory
        current_directory = state.get("current_directory")
        if not current_directory:
            raise ValueError("No directories left to retrieve context for.")
            
        # get collections
        code_collection = state["code_collection"]
        summary_collection = state["summary_collection"]
        root_directory = state["directory_path"]

        # compute relative directory for querying
        try:
            rel_dir = os.path.relpath(current_directory, root_directory)
        except ValueError:
            rel_dir = current_directory

        rel_dir = Path(rel_dir).as_posix()
        dir_name = Path(current_directory).name

        # create query text - we can experiment with different query formats, but for now
        # im just using relative directory and dir_name
        query_text = f"{rel_dir} {dir_name}" if rel_dir != "." else dir_name

        code_k = state["codebase_k"]
        summary_k = state["file_summary_k"]

        # Query both vector stores
        code_results = code_collection.query(
            query_texts=[query_text],
            n_results=code_k
        )

        summary_results = summary_collection.query(
            query_texts=[query_text],
            n_results=summary_k
        )

        # Process results
        existing_code_context = set(state.get("code_context", []))
        existing_summary_context = set(state.get("summary_context", []))

        code_docs = code_results.get("documents", [[]])[0]
        code_metas = code_results.get("metadatas", [[]])[0]

        summary_docs = summary_results.get("documents", [[]])[0]
        summary_metas = summary_results.get("metadatas", [[]])[0]

        prioritized_code = []
        fallback_code = []

        # Prioritize results in current directory, but also include results from relevant
        # directories outsied of current
        for doc, meta in zip(code_docs, code_metas):
            file_path = self._normalize_path(meta.get("file", ""))
            formatted = self._format_code_result(doc, meta, rel_dir)

            if self._is_in_directory(file_path, rel_dir):
                prioritized_code.append(formatted)
            else:
                fallback_code.append(formatted)

        prioritized_summary = []
        fallback_summary = []

        for doc, meta in zip(summary_docs, summary_metas):
            summary_path = self._normalize_path(meta.get("path", ""))
            formatted = self._format_summary_result(doc, meta, rel_dir)

            if self._is_in_directory(summary_path, rel_dir):
                prioritized_summary.append(formatted)
            else:
                fallback_summary.append(formatted)

        # Append results to context
        updated_code_context = list(state.get("code_context", []))
        updated_summary_context = list(state.get("summary_context", []))

        for item in prioritized_code + fallback_code:
            if item not in existing_code_context:
                updated_code_context.append(item)

        for item in prioritized_summary + fallback_summary:
            if item not in existing_summary_context:
                updated_summary_context.append(item)

        return {
            "current_directory": current_directory,
            "code_context": updated_code_context,
            "summary_context": updated_summary_context,
        }

    def context_analyser_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        @brief Evaluates whether sufficient retrieval context has been gathered for the current directory.
            This node is responsible for determining whether the retrieved context is adequate to generate
            a directory-level summary. It analyzes both code snippets and summary entries collected by the
            retriever node.

            The evaluation is performed using an LLM with structured output (`ContextAnalysisOutput`).
            The model examines the retrieved context and decides:

                - Whether the current code context is sufficient.
                - Whether the current summary context is sufficient.
                - Whether additional retrieval should be performed.

            If additional context is required, the node increases the retrieval parameters:
                - `codebase_k` (number of code snippets retrieved)
                - `file_summary_k` (number of summary entries retrieved)

            These updated values allow the retriever node to perform a deeper search during the next
            iteration of the agentic RAG loop.

            A safeguard is implemented using maximum retrieval limits. If the retrieval parameters reach
            their configured maximum values, the node forces the sufficiency flags to `True` so the workflow
            can progress to the summarization stage.
        @note
            If both `code_context` and `summary_context` are empty, the LLM call is skipped and the retrieval
            depth is increased automatically.
        @param state
            The current workflow state containing the directory being analyzed, previously retrieved
            context, and retrieval parameters.
        @return DirectoryGraphState
            Updated state containing:
                - sufficient_code_context: whether enough code snippets have been retrieved
                - sufficient_summary_context: whether enough summary entries have been retrieved
                - codebase_k: updated retrieval depth for code snippets
                - file_summary_k: updated retrieval depth for summaries
        @throws ValueError
            If no directories are available for context analysis.
        """
        current_directory = state.get("current_directory")
        if not current_directory:
            raise ValueError("No directories left to retrieve context for.")
        
        root_directory = state["directory_path"]

        try:
            rel_dir = os.path.relpath(current_directory, root_directory)
        except ValueError:
            rel_dir = current_directory

        rel_dir = Path(rel_dir).as_posix()

        code_context = state.get("code_context", [])
        summary_context = state.get("summary_context", [])

        max_codebase_k = 20
        max_file_summary_k = 20

        if not code_context and not summary_context:
            return {
                "sufficient_code_context": False,
                "sufficient_summary_context": False,
                "codebase_k": min(state["codebase_k"] + 2, max_codebase_k),
                "file_summary_k": min(state["file_summary_k"] + 2, max_file_summary_k),
            }

        structured_llm = self.llm.with_structured_output(ContextAnalysisOutput)

        messages = [("system", "You are a Senior Software Architect. You are deciding whether enough retrieval context has been gathered to write a directory-level summary."),
        ("user",f"""
        Current directory absolute path:
        {current_directory}

        Current directory relative path:
        {rel_dir}

        Current retrieval settings:
        - codebase_k: {state["codebase_k"]}
        - file_summary_k: {state["file_summary_k"]}

        Code context:
        {chr(10).join(code_context) if code_context else "None"}

        Summary context:
        {chr(10).join(summary_context) if summary_context else "None"}

        Decide:
        1. Is the code context sufficient?
        2. Is the summary context sufficient?
        3. If not, recommend small increases.

        Guidelines:
        - Prefer small increases, usually 1 to 5.
        - If the context is enough to write a reasonable directory summary, mark it sufficient.
        - Do not recommend negative increases.
        """)]

        analysis = self._invoke_with_retry(structured_llm, messages)

        code_increase = max(0, analysis.recommended_codebase_k_increase)
        summary_increase = max(0, analysis.recommended_file_summary_k_increase)

        next_codebase_k = state["codebase_k"]
        next_file_summary_k = state["file_summary_k"]

        if not analysis.sufficient_code_context:
            next_codebase_k = min(
                state["codebase_k"] + max(1, code_increase),
                max_codebase_k
            )

        if not analysis.sufficient_summary_context:
            next_file_summary_k = min(
                state["file_summary_k"] + max(1, summary_increase),
                max_file_summary_k
            )

        code_at_cap = next_codebase_k >= max_codebase_k
        summary_at_cap = next_file_summary_k >= max_file_summary_k

        return {
            "sufficient_code_context": analysis.sufficient_code_context or code_at_cap,
            "sufficient_summary_context": analysis.sufficient_summary_context or summary_at_cap,
            "codebase_k": next_codebase_k,
            "file_summary_k": next_file_summary_k,
        }

    def summarizer_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        @brief Generates a summary of the current directory based on retrieved context and updates the state with the summary.
        @param state Workflow state object containing the current directory and retrieved context.
        @return Updated state with directory summary in the form of a DirectoryOutput object.
        """
        
        if (isinstance(self.llm, GenericFakeChatModel)):
            output = self.llm.invoke("")
            return {
                "code_context": [], # Clear code and summary context and k after summarization so that the next retrieval starts fresh
                "summary_context": [],
                "sufficient_code_context": False,
                "sufficient_summary_context": False,
                "codebase_k": 10,
                "file_summary_k": 10,
                "directory_summary": DirectoryOutput(
                    directory_name = Path(state["current_directory"]).name,
                    directory_path = state["current_directory"],
                    purpose = output.content)
            }
        
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
            output = output = self._invoke_with_retry(strucured_llm, messages)

            print(f"Generated summary for directory {state['current_directory']}")

            return {
                "code_context": [], # Clear code and summary context and k after summarization so that the next retrieval starts fresh
                "summary_context": [],
                "sufficient_code_context": False,
                "sufficient_summary_context": False,
                "codebase_k": 10,
                "file_summary_k": 10,
                "directory_summary": output,
                "child_summaries": {current_dir: output} # Add the current summary to the child_summaries dict
            }
        except Exception as e:
            print(f"Error during summarization: {e}")
            return {
                "code_context": [], # Clear code and summary context and k after summarization so that the next retrieval starts fresh
                "summary_context": [],
                "sufficient_code_context": False,
                "sufficient_summary_context": False,
                "codebase_k": 10,
                "file_summary_k": 10,
                "directory_summary": DirectoryOutput(
                    directory_name = Path(state["current_directory"]).name,
                    directory_path = state["current_directory"],
                    purpose = f"Error generating summary: {e}")
            }

    def writer_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        @brief Writes the current directory's summary to a JSON file and updates the workflow state.
            Root directory summaries are saved under a `root_output` subdirectory.
        @param state Current workflow state containing `directory_summary`, `directories`, 
                    `codebase_name`, and `directory_path`.
        @return Updated state with:
                - `current_directory`: set to the next directory to process, or `None` if finished.
                - Summary JSON written to the appropriate output folder:
                    - Non-root directories: `directory_agent_output/<codebase_name>/`
                    - Root directory: `directory_agent_output/<codebase_name>/root_output/`
        """
        # creates directory_agent_output subdir 
        base_output_dir = "./agent/directory_agent_output"
        os.makedirs(base_output_dir, exist_ok=True)

        # create codebase subdir inside of directory_agent_output
        codebase_subdir = os.path.join(base_output_dir, f'{state["codebase_name"]}_gpt')
        os.makedirs(codebase_subdir, exist_ok=True)

        directory_summary = state['directory_summary']
        
        # create relative path from absolute
        rel_path = os.path.relpath(directory_summary.directory_path, state["directory_path"])

        # case for root level summary
        if rel_path == ".":
            final_dir = os.path.join(codebase_subdir, "root_output")
            os.makedirs(final_dir, exist_ok=True)

            safe_name = state["codebase_name"] + ".json"
            full_path = os.path.join(final_dir, safe_name)
        
        # case for non-root level summaries
        else:
            safe_name = Path(rel_path).as_posix().strip("./").replace("/", "_") + ".json"
            full_path = os.path.join(codebase_subdir, safe_name)
        
        # write summary into .JSON file
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(directory_summary.model_dump_json(indent=2))
        
        # move onto next directory
        if state["directories"]:
            next_dir = state["directories"].pop()
            state["current_directory"] = next_dir
        
        # case for when the directory that just finished is the last one (root)
        else:
            state["current_directory"] = None

        return state
        

    # Helper methods
    def _normalize_path(self, path_value: str) -> str:
        """
        @brief Normalizes a filesystem path to POSIX format.

        Converts the provided path to a forward-slash POSIX-style path to ensure
        consistent comparisons across operating systems.

        @param path_value The path to normalize.
        @return The normalized POSIX-style path, or an empty string if the input is empty.
        """
        if not path_value:
            return ""
        return Path(path_value).as_posix()

    def _is_in_directory(self, candidate_path: str, target_rel_dir: str) -> bool:
        """
        @brief Checks whether a file path belongs to a specified directory.

        Determines if the parent directory of the given path matches or is contained
        within the target relative directory.

        @param candidate_path The file path being evaluated.
        @param target_rel_dir The relative directory to check membership against.
        @return True if the path belongs to the directory or one of its subdirectories.
        """
        candidate_path = self._normalize_path(candidate_path)

        if target_rel_dir == ".":
            return True

        parent_dir = Path(candidate_path).parent.as_posix()
        return parent_dir == target_rel_dir or parent_dir.startswith(target_rel_dir + "/")

    def _format_code_result(self, doc: str, meta: dict, rel_dir: str) -> str:
        """
        @brief Formats a retrieved code chunk and its metadata for inclusion in context.

        Produces a structured string representation of a code snippet retrieved from
        the vector database, including metadata such as file location, container,
        namespace, and line numbers.

        @param doc The retrieved code snippet content.
        @param meta Metadata associated with the snippet.
        @param rel_dir The relative directory currently being processed.
        @return A formatted string representing the code context entry.
        """
        file_path = self._normalize_path(str(meta.get("file", "unknown")))

        return (
            f"[CODE CHUNK]\n"
            f"Directory: {rel_dir}\n"
            f"File: {file_path}\n"
            f"Container: {meta.get('container', 'unknown')}\n"
            f"Name: {meta.get('name', 'unknown')}\n"
            f"Type: {meta.get('type', 'unknown')}\n"
            f"Namespace: {meta.get('namespace', 'unknown')}\n"
            f"Lines: {meta.get('start_line', '?')}-{meta.get('end_line', '?')}\n"
            f"Content:\n{doc}"
        )

    def _format_summary_result(self, doc: str, meta: dict, rel_dir: str) -> str:
        """
        @brief Formats a retrieved summary entry and its metadata for context.

        Produces a structured representation of a summary node retrieved from the
        summary vector database, including its path, type, and parent information.

        @param doc The retrieved summary text.
        @param meta Metadata associated with the summary node.
        @param rel_dir The relative directory currently being processed.
        @return A formatted string representing the summary context entry.
        """
        summary_path = self._normalize_path(str(meta.get("path", "unknown")))

        return (
            f"[SUMMARY NODE]\n"
            f"Directory: {rel_dir}\n"
            f"Path: {summary_path}\n"
            f"Node Type: {meta.get('type', 'unknown')}\n"
            f"Name: {meta.get('name', 'unknown')}\n"
            f"Parent: {meta.get('parent', 'N/A')}\n"
            f"Content:\n{doc}"
        )

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
    
    def _invoke_with_retry(self, llm, messages, max_retries=5, base_delay=2):
        """
        Retry wrapper for LLM calls to handle rate limits.
        Uses exponential backoff.
        """
        attempt = 0

        while True:
            try:
                return llm.invoke(messages)

            except RateLimitError as e:
                attempt += 1
                if attempt > max_retries:
                    raise e

                wait = base_delay * (2 ** (attempt - 1))
                print(f"Rate limit hit. Retrying in {wait}s...")
                time.sleep(wait)

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
    