from agent.states.directory_agent_state import DirectoryGraphState
from agent.structured_output.directory_output import DirectoryOutput, ContextAnalysisOutput, JudgementOutput, BusinessRulesOutput
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from dotenv import load_dotenv
import os
import sys
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pathlib import Path
from collections import deque
import json

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
        builder.add_node("root_summarizer", self.root_summary_node)
        builder.add_node("judgement", self.judgement_node)
        builder.add_node("refinement", self.refinement_node)
        builder.add_node("business_rules_extractor", self.business_rules_node)
        builder.add_node("writer", self.writer_node)
        builder.add_node("rollup_writer", self.rollup_writer_node)

        # Set edges
        builder.set_entry_point("crawler")
        builder.add_edge("crawler", "retriever")
        builder.add_edge("retriever", "context_analyser")
        builder.add_conditional_edges(
            "context_analyser",
            lambda state: "root_summarizer" if state.get("current_directory") == state.get("directory_path")
            else ("summarizer" if state["sufficient_code_context"] and state["sufficient_summary_context"] else "retriever")
        )
        builder.add_edge("summarizer", "judgement")
        builder.add_edge("root_summarizer", "judgement")
        builder.add_conditional_edges(
            "judgement",
            lambda state: "business_rules_extractor" if state["summary_acceptable"] or state["refinement_attempts"] >= 2 else "refinement"
        )
        builder.add_edge("refinement", "judgement")
        builder.add_edge("business_rules_extractor", "writer")
        builder.add_conditional_edges(
            "writer",
            lambda state: "retriever" if state["current_directory"] else "rollup_writer"
        )
        builder.add_edge("rollup_writer", END)

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
            "summary_collection": summary_collection,
            "summary_acceptable": False,
            "summary_feedback": "",
            "refinement_attempts": 0,
            "accumulated_business_rules": {}
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
        
        total_dirs = len(discovered_directories)
        first_dir = discovered_directories.pop()
        return {
            "directories": deque(discovered_directories),
            "total_number_of_directories": total_dirs,
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

        analysis = structured_llm.invoke(messages)

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
                "directory_summary": DirectoryOutput(
                    directory_name = Path(state["current_directory"]).name,
                    directory_path = state["current_directory"],
                    purpose = output.content)
            }
        
        try:
            # Structure LLM output
            structured_llm = self.llm.with_structured_output(DirectoryOutput)

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
                        {formatted_child_summaries if formatted_child_summaries else "None"}

                        2. FILE-LEVEL SUMMARIES:
                        {summary_context if summary_context else "None"}

                        3. CODE SNIPPETS:
                        {code_context if code_context else "None"}

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
            output = structured_llm.invoke(messages)

            print(f"Generated summary for directory {state['current_directory']}")

            return {
                "directory_summary": output
            }
        except Exception as e:
            print(f"Error during summarization: {e}")
            return {
                "directory_summary": DirectoryOutput(
                    directory_name = Path(state["current_directory"]).name,
                    directory_path = state["current_directory"],
                    purpose = f"Error generating summary: {e}")
            }
        
    def root_summary_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        if (isinstance(self.llm, GenericFakeChatModel)):
            output = self.llm.invoke("")
            return {
                "directory_summary": DirectoryOutput(
                    directory_name = Path(state["current_directory"]).name,
                    directory_path = state["current_directory"],
                    purpose = output.content)
        }

        try:
            structured_llm = self.llm.with_structured_output(DirectoryOutput)
            # Gather all relevant context for summarization
            current_dir = state["current_directory"]
            child_summaries = self._get_child_directory_summaries(current_dir, state["child_summaries"])
            formatted_child_summaries = self._format_child_summaries(child_summaries)
            summary_context = "\n\n".join(state["summary_context"])
            code_context = "\n\n".join(state["code_context"])
            
            system_message = """You are a principal software architect writing a comprehensive root-level codebase summary.
Your audience includes technical leads, stakeholders, and new developers seeking to understand the entire system.
Your task is to synthesize information about all major subsystems into a cohesive overview of what the codebase is, 
how its parts work together, and what the overall system delivers."""

            prompt = f"""ROOT DIRECTORY TO ANALYZE: {state['current_directory']}

INPUT DATA (in order of priority):
1. CHILD DIRECTORY SUMMARIES (primary basis for root-level synthesis):
{formatted_child_summaries if formatted_child_summaries else "None"}

2. FILE-LEVEL SUMMARIES (secondary — use to fill gaps and provide detail):
{summary_context if summary_context else "None"}

3. CODE SNIPPETS (tertiary — reference only if necessary for clarification):
{code_context if code_context else "None"}

TASK:
Write a comprehensive root-level summary of the entire codebase that explains the system as a whole to someone new to the project.

YOUR SUMMARY MUST ANSWER:
1. What is this codebase? (high-level purpose, problem domain, main use case)
2. How are the major subsystems organized? (not just what each does, but how they relate and depend on each other)
3. What are the main data flows or processing pipelines? (how does information move through the system?)
4. What are the core capabilities the system provides? (end user or API perspective, not implementation details)
5. What are the notable architectural patterns or constraints? (why is it structured this way?)

RESPONSE SHAPE:
- Purpose: multiple dense paragraphs covering the above five questions. Aim comprehensiveness over conceiseness, but avoid unnecessary detail. Use concrete language and specific examples from the provided context to support your statements.
- Responsibilities: a list of the major capability areas or domains the system owns (5-10 items), named concisely.
  Example good names: "Table formatting and rendering", "Column alignment and text wrapping", "Data source abstraction"
  Example bad names: "formatting", "utilities", "core logic"

QUALITY BAR:
- Synthesize across subsystems. Do not recap each child directory in sequence.
- Explain relationships and interdependencies between major parts, not just their isolated roles.
- Be specific and concrete. Avoid vague phrases like "provides functionality", "handles processing", or "manages data".
- If child summaries are thin or conflicting, acknowledge the gap rather than speculating.
- Do not invent architectural patterns or design decisions not supported by the provided context.

DIFFERENCE FROM INDIVIDUAL DIRECTORY SUMMARIES:
This is a root-level synthesis. It should be noticeably more comprehensive and higher-level than individual directory summaries.
Show how the parts connect and the overall shape of the system, not just what each part does in isolation."""
    
            messages = [("system", system_message), ("user", prompt)]

            # Generate summary using LLM
            output = structured_llm.invoke(messages)

            print(f"Generated root summary for directory {state['current_directory']}")

            return {
                "directory_summary": output
            }
            
        
        except Exception as e:
            print(f"Error during summarization: {e}")
            return {
                "directory_summary": DirectoryOutput(
                    directory_name = Path(state["current_directory"]).name,
                    directory_path = state["current_directory"],
                    purpose = f"Error generating summary: {e}")
        }

    def business_rules_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        @brief Extracts cross-file business rules for the current directory.
            Uses a targeted query of the summary vector store filtered to the current
            directory to ensure completeness, then prompts the LLM to identify rules
            that only emerge when multiple files are considered together.
        @param state Workflow state containing the finalized directory summary and
                    vector store handles.
        @return Updated state with an entry added to accumulated_business_rules for
                the current directory.
        """
        current_dir = state["current_directory"]

        root_directory = state["directory_path"]
        try:
            rel_dir = os.path.relpath(current_dir, root_directory)
        except ValueError:
            rel_dir = current_dir
        rel_dir = Path(rel_dir).as_posix()

        if isinstance(self.llm, GenericFakeChatModel):
            return {
                "accumulated_business_rules": {
                    current_dir: BusinessRulesOutput(
                        directory_name=Path(current_dir).name,
                        directory_path=rel_dir,
                        observed_rules=[],
                        inferred_rules=[]
                    )
                }
            }

        try:
            structured_llm = self.llm.with_structured_output(BusinessRulesOutput)

            summary_collection = state["summary_collection"]
            directory_summary = state["directory_summary"]

            # Fetch ALL documents from the summary collection, then post-filter
            # to the current directory. This guarantees completeness unlike the
            # RAG top-k approach used by retriever_node.
            all_results = summary_collection.get(include=["documents", "metadatas"])
            docs = all_results.get("documents", [])
            metas = all_results.get("metadatas", [])

            directory_file_summaries = []
            matched_file_paths = set()
            for doc, meta in zip(docs, metas):
                summary_path = self._normalize_path(str(meta.get("path", "")))
                if self._matches_directory_summary_path(
                    candidate_path=summary_path,
                    target_abs_dir=current_dir,
                    root_directory=root_directory,
                    codebase_name=state["codebase_name"]
                ):
                    directory_file_summaries.append(
                        self._format_summary_result(doc, meta, rel_dir)
                    )
                    matched_file_paths.add(Path(summary_path).name)

            if not directory_file_summaries:
                print(f"No file summaries found for {current_dir}, skipping business rules extraction.")
                return {
                    "accumulated_business_rules": {
                        current_dir: BusinessRulesOutput(
                            directory_name=Path(current_dir).name,
                            directory_path=rel_dir,
                            observed_rules=[],
                            inferred_rules=[]
                        )
                    }
                }

            if len(matched_file_paths) < 2:
                print(f"Only one unique file found for {current_dir}, skipping cross-file business rules extraction.")
                return {
                    "accumulated_business_rules": {
                        current_dir: BusinessRulesOutput(
                            directory_name=Path(current_dir).name,
                            directory_path=rel_dir,
                            observed_rules=[],
                            inferred_rules=[]
                        )
                    }
                }

            formatted_file_summaries = "\n\n".join(directory_file_summaries)

            system_message = """You are a business analyst extracting business rules and domain policies from a software system.
                                Your task is to identify rules that exist *between* files — policies, constraints, or behaviors that only 
                                emerge when multiple files or components are considered together. Focus strictly on what the code and summaries actually enforce, 
                                not general software patterns."""


            prompt = f"""DIRECTORY: {current_dir}

                        DIRECTORY SUMMARY:
                        {directory_summary.purpose}

                        FILE-LEVEL SUMMARIES FOR THIS DIRECTORY:
                        {formatted_file_summaries}

                        TASK:
                        Identify the business rules that exist *between* files — policies, constraints, or behaviors that only emerge when multiple files or components are considered together
                        A business rule is a constraint, policy, or behavior that the system guarantees to its users — stated in terms of WHAT the system does, not HOW the code implements it.
                        Do not list rules that are entirely contained within a single file.

                        State rules in plain language that a non-technical stakeholder could understand.

                        OBSERVED RULES:
                        Rules that are directly and explicitly evidenced by the file summaries above.
                        List each as a single, concrete statement of what the system requires, allows, or prevents across multiple files.

                        INFERRED RULES:
                        Rules that are implied by the system's behavior across the files but not explicitly named.
                        Begin each entry with "Inference:" and describe the implied rule in plain, non-technical language.

                        EXAMPLES OF GOOD CROSS-FILE BUSINESS RULES:
                        - "A user cannot place an order unless their account has been verified and their payment method has been approved."
                        - "Discount codes can only be applied once per customer per transaction, and the discount amount must not exceed the order total."
                        - "All exported reports must use the same currency format and rounding rules that are applied during transaction processing."

                        EXAMPLES OF BAD RULES (do NOT produce these):
                        - "Every row must have the same number of columns as the header." (this is a single-file rule, not cross-file)
                        - "The From<T> method uses reflection to map properties." (describes implementation mechanism)
                        - "GetTextWidth calculates Unicode-aware widths." (technical implementation detail)
                        - "The validation rules defined in the configuration module are enforced by the processing module." (describes code architecture, not a business rule)
                        - "The system provides functionality for data processing." (too vague)

                        CONSTRAINTS:
                        - Do not fabricate rules. Every rule must be grounded in the provided summaries.
                        - If no cross-file buisness rules are visible, return empty lists — do not put business rules that are conatained to a single file.
                        - Be specific. Instead of "enforces validation", say what is validated and what the constraint is.
                        - Prefer plain, non-technical language. Avoid referencing programming constructs like method signatures, design patterns, or language-specific features.
                        - Do not give evidence or reasoning in the output — only list the rules themselves in the structured format."""

            messages = [("system", system_message), ("user", prompt)]
            output = structured_llm.invoke(messages)

            # Manually set directory_name and directory_path for consistency
            output.directory_name = Path(current_dir).name
            output.directory_path = rel_dir

            print(f"Extracted business rules for directory {current_dir}")
            return {
                "accumulated_business_rules": {current_dir: output}
            }

        except Exception as e:
            print(f"Error during business rules extraction for {state['current_directory']}: {e}")
            return {
                "accumulated_business_rules": {
                    state["current_directory"]: BusinessRulesOutput(
                        directory_name=Path(state["current_directory"]).name,
                        directory_path=rel_dir,
                        observed_rules=[],
                        inferred_rules=[]
                    )
                }
            }

    def judgement_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        @brief Evaluates the quality of the generated directory summary and determines if it meets the required standards.
        @param state Workflow state object containing the generated directory summary.
        @return Updated state with a flag indicating whether the summary is satisfactory or if it needs to be regenerated.
        """
        current_directory = state.get("current_directory")
        if not current_directory:
            raise ValueError("No current directory available for summary judgement.")

        summary = state.get("directory_summary")
        if not summary:
            raise ValueError("No directory summary available for judgement.")
        
        # get context for judgement
        structured_llm = self.llm.with_structured_output(JudgementOutput)
        child_summaries = self._get_child_directory_summaries(current_directory, state["child_summaries"])
        formatted_child_summaries = self._format_child_summaries(child_summaries)
        summary_context = "\n\n".join(state.get("summary_context", []))
        code_context = "\n\n".join(state.get("code_context", []))

        messages = [
            ("system", """You are a Senior Software Architect. 
             Your task is to evaluate whether the summary of a directory is actually useful, specific, and grounded in 
             the provided context."""),
            ("user", f"""
            DIRECTORY:
            {current_directory}

            GENERATED SUMMARY:
            directory_name: {summary.directory_name}
            directory_path: {summary.directory_path}
            purpose: {summary.purpose}
            responsibilities: {summary.responsibilities}

            CONTEXT USED TO GENERATE THE SUMMARY:

            CHILD DIRECTORY SUMMARIES:
            {formatted_child_summaries if formatted_child_summaries else "None"}

            FILE-LEVEL SUMMARIES:
            {summary_context if summary_context else "None"}

            CODE SNIPPETS:
            {code_context if code_context else "None"}

            EVALUATION CRITERIA:
            - The purpose must not be vague.
            - The summary must say what the directory is actually for.
            - The summary should reflect evidence from the context.
            - Responsibilities should be concrete when possible.
            - Reject generic filler like 'contains important components' unless it clearly explains which components and why.
            - If the summary is weak but salvageable, provide specific improvement instructions.

            Return structured output only.
            """)
        ]

        judgement = structured_llm.invoke(messages)
        judgement_feedback = judgement.feedback if judgement.feedback else ""

        return {
            "summary_acceptable": judgement.summary_acceptable,
            "summary_feedback": judgement_feedback
        }
    
    def refinement_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        @brief Refines the generated directory summary based on feedback from the judgement node.
        @param state Workflow state object containing the generated directory summary and feedback from the judgement node.
        @return Updated state with a refined directory summary that addresses the feedback provided by the judgement node.
        """
        current_attempts = state.get("refinement_attempts", 0) + 1
        print(f"Attempting refinement for directory {state['current_directory']}")
        try:
            current_directory = state.get("current_directory")
            if not current_directory:
                raise ValueError("No current directory available for summary refinement.")

            summary = state.get("directory_summary")
            if not summary:
                raise ValueError("No directory summary available for refinement.")
            
            feedback = state.get("summary_feedback", "")
            if not feedback:
                raise ValueError("No feedback available for summary refinement.")
            
            # Gather all relevant context for summarization
            child_summaries = self._get_child_directory_summaries(current_directory, state["child_summaries"])
            formatted_child_summaries = self._format_child_summaries(child_summaries)
            summary_context = "\n\n".join(state["summary_context"])
            code_context = "\n\n".join(state["code_context"])

            structured_llm = self.llm.with_structured_output(DirectoryOutput)
            messages = [
                ("system", """You are a Senior Software Architect. 
                Your task is to refine a previously generated directory summary based on specific feedback that identifies weaknesses in the original summary."""),
                ("user", f"""
                DIRECTORY:
                {current_directory}

                directory_name: {summary.directory_name}
                directory_path: {summary.directory_path}

                CONTEXT USED TO GENERATE THE SUMMARY:
                CHILD DIRECTORY SUMMARIES:
                {formatted_child_summaries if formatted_child_summaries else "None"}

                FILE-LEVEL SUMMARIES:
                {summary_context if summary_context else "None"}

                CODE SNIPPETS:
                {code_context if code_context else "None"}

                ORIGINAL SUMMARY:
                purpose: {summary.purpose}
                responsibilities: {summary.responsibilities}

                FEEDBACK FOR IMPROVEMENT:
                {feedback}

                INSTRUCTIONS:
                1. Amend the provided summary based on the feedback. Address any identified weaknesses or vagueness.
                2. If feedback mentions 'too vague', provide concrete examples: 
                    E.g. 'Contains utilities' → 'Contains string formatting utilities (case conversion, pluralization)'"
                3. Ensure that the refined summary is specific, useful, and grounded in the context. There must be no statements which contradict each other or the provided context.
                4. Amend only sections for which there is feedback. If a section is not mentioned in the feedback, keep it unchanged.
                """)
            ]

            refined_summary = structured_llm.invoke(messages)

            return {
                "directory_summary": refined_summary,
                "refinement_attempts": current_attempts
            }
        except Exception as e:
            print(f"Error during summary refinement: {e}")
            return {
                "directory_summary": state.get("directory_summary"), # If refinement fails, keep the original summary
                "refinement_attempts": current_attempts
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
        base_output_dir = state.get("output_directory", "./agent/directory_agent_output")

        os.makedirs(base_output_dir, exist_ok=True)

        # create codebase subdir inside of directory_agent_output
        codebase_subdir = os.path.join(base_output_dir, state["codebase_name"])
        os.makedirs(codebase_subdir, exist_ok=True)

        directory_summary = state['directory_summary']
        current_dir = state["current_directory"]
        
        # Determine root/non-root from workflow state, not model-generated output.
        rel_path = os.path.relpath(current_dir, state["directory_path"])
        rel_path_normalized = Path(rel_path).as_posix()
        is_root_summary = rel_path_normalized in {".", "./"}

        # case for root level summary
        if is_root_summary:
            final_dir = os.path.join(codebase_subdir, "root_output")
            os.makedirs(final_dir, exist_ok=True)

            root_name = (state.get("codebase_name") or Path(state["directory_path"]).name or "root").strip()
            safe_name = root_name + ".json"
            full_path = os.path.join(final_dir, safe_name)
        
        # case for non-root level summaries
        else:
            rel_name = rel_path_normalized.strip("./").replace("/", "_")
            if not rel_name:
                rel_name = Path(current_dir).name or "unnamed_directory"
            safe_name = rel_name + ".json"
            full_path = os.path.join(codebase_subdir, safe_name)
        
        # write summary into .JSON file
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(directory_summary.model_dump_json(indent=2))
        
        # move onto next directory
        if state["directories"]:
            next_dir = state["directories"].pop()

        # case for when the directory that just finished is the last one (root)
        else:
            next_dir = None

        return {
            "code_context": [],
            "summary_context": [],
            "sufficient_code_context": False,
            "sufficient_summary_context": False,
            "codebase_k": 10,
            "file_summary_k": 10,
            "summary_acceptable": False,
            "summary_feedback": "",
            "refinement_attempts": 0,
            "current_directory": next_dir,
            "child_summaries": {current_dir: directory_summary}
        }

    def rollup_writer_node(self, state: DirectoryGraphState) -> DirectoryGraphState:
        """
        @brief Writes the accumulated business rules for all processed directories to a
            single consolidated JSON file once the full codebase traversal is complete.
        @param state Workflow state containing accumulated_business_rules and codebase_name.
        @return Empty state update (no state fields are modified).
        """
        base_output_dir = state.get("output_directory", "./agent/directory_agent_output")
        codebase_subdir = os.path.join(base_output_dir, state["codebase_name"])
        rules_dir = os.path.join(codebase_subdir, "business_rules")
        os.makedirs(rules_dir, exist_ok=True)

        output_path = os.path.join(rules_dir, "business_rules.json")
        accumulated = state.get("accumulated_business_rules", {})
        serialized = {dir_path: rules.model_dump() for dir_path, rules in accumulated.items()}

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2)

        print(f"Business rules written to {output_path}")
        return {}

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

    def _matches_directory_summary_path(self, candidate_path: str, target_abs_dir: str, root_directory: str, codebase_name: str) -> bool:
        """
        @brief Matches summary metadata paths against the current directory, even when
            stored paths use mixed formats.

        Summary metadata in the collection may be stored as:
        - absolute source paths
        - paths prefixed with the codebase name
        - shorter relative paths from an older export format

        This helper canonicalizes those variants into possible relative parent
        directories and checks them against the current directory's relative path.

        @param candidate_path The summary metadata path to evaluate.
        @param target_abs_dir The absolute path of the directory currently being processed.
        @param root_directory The absolute root path of the codebase.
        @param codebase_name The name of the codebase being processed.
        @return True if the summary path should be considered part of the current directory.
        """
        candidate_path = self._normalize_path(candidate_path)
        if not candidate_path:
            return False

        target_rel_dir = self._normalize_path(os.path.relpath(target_abs_dir, root_directory)).strip("./") or "."
        candidate_parent = Path(candidate_path).parent.as_posix().strip("./") or "."

        candidate_parent_options = {candidate_parent}

        if os.path.isabs(candidate_path):
            try:
                abs_rel_parent = self._normalize_path(os.path.relpath(Path(candidate_path), root_directory))
                candidate_parent_options.add((Path(abs_rel_parent).parent.as_posix().strip("./") or "."))
            except ValueError:
                pass

        codebase_prefix = f"{codebase_name}/"
        if candidate_path.startswith(codebase_prefix):
            stripped_parent = Path(candidate_path[len(codebase_prefix):]).parent.as_posix().strip("./") or "."
            candidate_parent_options.add(stripped_parent)

        for candidate_parent_option in candidate_parent_options:
            if target_rel_dir == ".":
                return True
            if candidate_parent_option == target_rel_dir:
                return True
            if candidate_parent_option.startswith(target_rel_dir + "/"):
                return True
            if target_rel_dir.endswith("/" + candidate_parent_option):
                return True

        return False

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
    