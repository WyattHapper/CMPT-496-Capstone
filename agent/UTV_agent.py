"""
@file UTV_agent.py
@brief Defines the UTVAgent, a LangGraph-based agent for validating generated unit tests from business rules.
@details Implements a validator-writer workflow that re-checks tests already saved in unit_tests.json:
- Writes each candidate xUnit test to its own file in the codebase's test project
- Builds them; a test that does not compile gets its own compiler errors and matching code from the
  codebase back to the AI for repair, and is dropped if it still fails (agent/test_harness.py)
- Runs the tests that compile and writes an html report
- Writes validated tests, discarded tests (with the reason) and a summary to JSON

The same checks run automatically at the end of unit test generation (UTAgent.runner_node).
This agent is for re-checking afterwards, e.g. from the "validate only" button.
"""
import logging
logger = logging.getLogger(__name__)
from agent.states.UTV_agent_state import UTVGraphState
from agent.structured_output.UTV_output import UnitTest
from langgraph.graph import StateGraph, START, END
from agent.llm import make_llm
from agent.test_harness import check_tests, make_cases, make_fixer, write_results
import os
import sys
import asyncio
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pathlib import Path
from backend.progress_logging import progress
from utils.chroma_utils import collection_name

# Code chunks retrieved per broken test for the repair prompt.
REPAIR_CODEBASE_K = 15


class UTVAgent:
    """
    @brief LangGraph-based agent for validating generated unit tests.

    @details
    The UTVAgent constructs and executes a LangGraph workflow that:
    - Writes candidate xUnit tests into the selected codebase test project, one file per test
    - Builds them, has the AI repair the ones that do not compile, and drops what it cannot fix
    - Runs the rest with `dotnet test`
    - Writes validated and discarded test metadata to JSON output files
    """

    def __init__(self, model=None):
        """
        @brief Initializes the UTVAgent with a specified language model.
        @param model An optional language model to use. If not provided, defaults to gemini-3-flash-preview.
        """
        progress("Intializing unit test validation agent...", 5)
        if model is None:
            self.llm = make_llm()
        else:
            self.llm = model
        self.graph = self.build_graph()

    def build_graph(self) -> StateGraph:
        """
        @brief Constructs the StateGraph that defines the UTVAgent workflow.
        @return A compiled StateGraph object.

        @details
        Graph structure:
            validator → writer → END
        """

        builder = StateGraph(UTVGraphState)

        # Set nodes
        builder.add_node("validator", self.validator_node)
        builder.add_node("writer", self.writer_node)

        # Set edges
        builder.set_entry_point("validator")
        builder.add_edge("validator", "writer")
        builder.add_edge("writer", END)
        return builder.compile()

    def run(self, input_tests: list[UnitTest], codebase_name: str, codebase_path: str):
        """
        @brief Executes the UTVAgent workflow.
        @param input_tests List of UnitTest candidates, as saved in unit_tests.json.
        @param codebase_name Name of the target codebase, used to look up the correct ChromaDB collection.
        @param codebase_path Filesystem path of the target codebase.
        @return Final state of the graph after execution.
        """
        progress(
            "Running unit test validation pipeline...",
            5
        )
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent.parent

        db_dir = (base_dir / "vectorStores").resolve()

        # Code context only improves repairs; a codebase without a code
        # database (e.g. one in a language the parser does not support) is
        # still validated, just with less help for the AI.
        try:
            embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            client = chromadb.PersistentClient(path=str(db_dir))
            code_collection = client.get_collection(
                name=collection_name(codebase_name, "code"),
                embedding_function=embedding_fn
            )
            progress("Loaded code database.", 10)
        except Exception as e:
            code_collection = None
            progress(f"No code database for {codebase_name}; repairing without code context. ({e})", 10)

        initial_state = {
            "current_tests": input_tests,
            "test_run": None,
            "code_collection": code_collection,
            "codebase_name": codebase_name,
            "codebase_path": codebase_path,
            "output_directory": "./agent/UT_agent_output",
        }

        self._loop = asyncio.new_event_loop()
        try:
            return self.graph.invoke(initial_state)
        finally:
            self._loop.close()
            self._loop = None

    def validator_node(self, state: UTVGraphState) -> UTVGraphState:
        """
        @brief Writes, builds, repairs and runs the candidate tests.

        @details See agent/test_harness.py. Only tests that do not compile are sent to the AI,
        each with its own compiler errors; tests that compile but fail an assertion are kept
        and reported, since the failure may be a real bug in the codebase.

        @param state Current workflow state containing current_tests.
        @return Updated state with test_run.
        """
        progress(
            "Validating unit tests...",
            20
        )
        codebase_name = state["codebase_name"]
        codebase_path = state["codebase_path"]
        base_output_dir = state.get("output_directory", "./agent/UT_agent_output")
        codebase_subdir = os.path.join(base_output_dir, codebase_name)
        code_collection = state.get("code_collection")

        cases, rejected = make_cases(
            "UT",
            [(test.id, test) for test in state["current_tests"]],
            body_of=lambda test: test.unit_test,
            imports_of=lambda test: test.imports,
        )

        def context_for(case):
            if code_collection is None or not code_collection.count():
                return ""
            test = case.source
            query_text = f"{test.rule} {' '.join(case.errors[:3])}"
            results = code_collection.query(
                query_texts=[query_text],
                n_results=min(REPAIR_CODEBASE_K, code_collection.count())
            )
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            return "\n\n".join(
                self._format_code_result(doc, meta, test.source_directory)
                for doc, meta in zip(docs, metas)
            )

        test_run = check_tests(
            "Unit",
            "UT",
            cases,
            rejected,
            codebase_path,
            codebase_name,
            codebase_subdir,
            fix=make_fixer(self.llm, context_for),
            loop=self._loop,
        )

        return {"test_run": test_run}

    def writer_node(self, state: UTVGraphState) -> UTVGraphState:
        """
        @brief Writes the validation results to JSON output files.

        @details
        Writes validated_tests.json, discarded_tests.json and test_report.json under
        {output_directory}/{codebase_name}/, next to unit_test_report.html.
        Runs exactly once at the end of the graph.

        @param state Current workflow state containing test_run.
        @return Empty dict (terminal node).
        """
        progress(
            "Writing validated and discarded unit tests...",
            90
        )

        codebase_name = state["codebase_name"]
        base_output_dir = state.get("output_directory", "./agent/UT_agent_output")
        codebase_subdir = os.path.join(base_output_dir, codebase_name)
        test_run = state["test_run"]

        write_results(
            test_run,
            codebase_subdir,
            lambda case: dict(case.source.model_dump(), imports=case.imports, unit_test=case.body),
        )

        progress(test_run.message(), 100, True)
        return {}

    # Helper methods

    def _normalize_path(self, path_value: str) -> str:
        """
        @brief Normalizes a filesystem path to POSIX format.
        @param path_value The path to normalize.
        @return The normalized POSIX-style path, or an empty string if the input is empty.
        """
        if not path_value:
            return ""
        return Path(path_value).as_posix()

    def _is_in_directory(self, candidate_path: str, target_rel_dir: str) -> bool:
        """
        @brief Checks whether a file path belongs to a specified directory.
        @param candidate_path The file path being evaluated.
        @param target_rel_dir The relative directory to check membership against.
        @return True if the path belongs to the directory or one of its subdirectories.
        """
        candidate_path = self._normalize_path(candidate_path)

        if target_rel_dir == ".":
            return True

        parent_dir = Path(candidate_path).parent.as_posix()
        return parent_dir == target_rel_dir or parent_dir.startswith(target_rel_dir + "/")

    def _is_from_source_file(self, candidate_path: str, source_file_paths: list[str]) -> bool:
        """
        @brief Checks whether a retrieved result's file path matches any of the rule's source files.
        @param candidate_path The file path from the retrieved result's metadata.
        @param source_file_paths List of source file paths from the CondensedRule.
        @return True if the candidate matches any source file path.
        """
        candidate_normalized = self._normalize_path(candidate_path)
        for source_path in source_file_paths:
            source_normalized = self._normalize_path(source_path)
            if candidate_normalized == source_normalized:
                return True
            # Suffix match on path boundary (must align to a '/' separator)
            if (candidate_normalized.endswith("/" + source_normalized)
                    or source_normalized.endswith("/" + candidate_normalized)):
                return True
        return False

    def _format_code_result(self, doc: str, meta: dict, source_directory: str) -> str:
        """
        @brief Formats a retrieved code chunk and its metadata for inclusion in context.
        @param doc The retrieved code snippet content.
        @param meta Metadata associated with the snippet.
        @param source_directory The source directory of the current rule.
        @return A formatted string representing the code context entry.
        """
        file_path = self._normalize_path(str(meta.get("file", "unknown")))

        return (
            f"[CODE CHUNK]\n"
            f"Directory: {source_directory}\n"
            f"File: {file_path}\n"
            f"Container: {meta.get('container', 'unknown')}\n"
            f"Name: {meta.get('name', 'unknown')}\n"
            f"Type: {meta.get('type', 'unknown')}\n"
            f"Namespace: {meta.get('namespace', 'unknown')}\n"
            f"Lines: {meta.get('start_line', '?')}-{meta.get('end_line', '?')}\n"
            f"Content:\n{doc}"
        )

    def _format_summary_result(self, doc: str, meta: dict, source_directory: str) -> str:
        """
        @brief Formats a retrieved summary entry and its metadata for context.
        @param doc The retrieved summary text.
        @param meta Metadata associated with the summary node.
        @param source_directory The source directory of the current rule.
        @return A formatted string representing the summary context entry.
        """
        summary_path = self._normalize_path(str(meta.get("path", "unknown")))

        return (
            f"[SUMMARY NODE]\n"
            f"Directory: {source_directory}\n"
            f"Path: {summary_path}\n"
            f"Node Type: {meta.get('type', 'unknown')}\n"
            f"Name: {meta.get('name', 'unknown')}\n"
            f"Parent: {meta.get('parent', 'N/A')}\n"
            f"Content:\n{doc}"
        )
