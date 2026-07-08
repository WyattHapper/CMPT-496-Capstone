"""
@file UT_agent.py
@brief Defines the UTAgent, a LangGraph-based agent for generating Unit Tests based of business rules.
@details Implements a retriever-generator-writer workflow that takes validated business rules from BR_agent output,
generates unit tests and writes the results to JSON.
"""

from agent.states.UT_agent_state import UTGraphState
from agent.structured_output.UT_output import (
    ValidatedRule, UnitTest
)
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import sys
import json
import asyncio
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pathlib import Path
from collections import defaultdict

MAX_CONCURRENCY = 10
DEFAULT_CODEBASE_K = 15
DEFAULT_FILE_SUMMARY_K = 5
MAX_CODEBASE_K = 30
MAX_FILE_SUMMARY_K = 10


class UTAgent:
    """
    @brief LangGraph-based agent for generating unit tests based on business rules.

    @details
    The UTAgent constructs and executes a LangGraph workflow that:
    - Retrieves file and summary context for validated business rules from BR_agent output.
    - Generates unit tests for each validated rule.
    - Writes the generated unit tests to JSON output files.
    """

    def __init__(self, model=None):
        """
        @brief Initializes the UTAgent with a specified language model.
        @param model An optional language model to use. If not provided, defaults to gemini-3-flash-preview.
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

    def build_graph(self) -> StateGraph:
        """
        @brief Constructs the StateGraph that defines the UTAgent workflow.
        @return A compiled StateGraph object.

        @details
        Graph structure:
            retriever → test_generator → writer → END

        Conditional routing from condenser and validator:
            - If current_rules is non-empty → retriever
            - If current_rules is empty (all rules processed) → writer
        """

        builder = StateGraph(UTGraphState)

        # Set nodes
        builder.add_node("retriever", self.retriever_node)
        builder.add_node("test_generator", self.test_generator_node)
        builder.add_node("writer", self.writer_node)

        # Set edges
        builder.set_entry_point("retriever")
        builder.add_edge("retriever", "test_generator")
        builder.add_edge("test_generator", "writer")
        builder.add_edge("writer", END)

        return builder.compile()

    def run(self, validated_rules: dict[str, list[ValidatedRule]], codebase_name: str, codebase_path: str, output_dir=None):
        """
        @brief Executes the UTAgent workflow.
        @param input_rules Dictionary of validated business rules from BR_agent output. Keys are file or directory paths,
               values are lists of ValidatedRule objects.
        @param codebase_name Name of the target codebase, used to look up the correct ChromaDB collections.
        @return Final state of the graph after execution.
        """
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent.parent

        db_dir = (base_dir / "vectorStores").resolve()

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
            "validated_rules": validated_rules,
            "unit_tests": [],
            "rule_contexts": {},
            "codebase_k": DEFAULT_CODEBASE_K,
            "file_summary_k": DEFAULT_FILE_SUMMARY_K,
            "code_collection": code_collection,
            "summary_collection": summary_collection,
            "codebase_name": codebase_name,
            "codebase_path": codebase_path,
            "output_directory": os.path.join(output_dir or ".", "agent", "UT_agent_output")
        }

        self._loop = asyncio.new_event_loop()
        try:
            return self.graph.invoke(initial_state)
        finally:
            self._loop.close()
            self._loop = None
    
    def retriever_node(self, state: UTGraphState) -> UTGraphState:
        """
        @brief Retrieves relevant code snippets and file summaries for all current validated business rules.

        @details
        Iterates over every rule in validated_rules and queries two ChromaDB vector
        collections (code and summary) for each. Results are prioritized in three tiers:
            1. Results from the rule's source files (highest priority)
            2. Results from the rule's source directory
            3. All other results (fallback)

        Per-rule context is stored in rule_contexts[rule.id] and accumulates across
        retrieval iterations for the same rule (deduplication against prior results).
        Retrieval depth is controlled by codebase_k and file_summary_k, which may be
        increased by the validator on "need_more_context" decisions.

        @param state Current workflow state containing validated_rules and retrieval parameters.
        @return Updated state with rule_contexts populated/extended.
        @raises ValueError If current_rules is empty.
        """
        validated_rules = state.get("validated_rules", [])
        if not validated_rules:
            raise ValueError("No validated rules to retrieve context for.")

        code_collection = state["code_collection"]
        summary_collection = state["summary_collection"]
        code_k = state["codebase_k"]
        summary_k = state["file_summary_k"]

        existing_contexts = state.get("rule_contexts", {})
        updated_contexts = dict(existing_contexts)

        for rule in validated_rules:
            source_directory = rule.source_directory
            source_file_paths = rule.source_file_paths
            query_text = f"{rule.rule} {source_directory}"

            safe_code_k = min(code_k, code_collection.count()) or 1
            safe_summary_k = min(summary_k, summary_collection.count()) or 1

            code_results = code_collection.query(
                query_texts=[query_text],
                n_results=safe_code_k
            )
            summary_results = summary_collection.query(
                query_texts=[query_text],
                n_results=safe_summary_k
            )

            # Get existing per-rule context for deduplication (str key for JSON serialization safety)
            rule_key = str(rule.id)
            rule_ctx = updated_contexts.get(rule_key, {"code_context": [], "summary_context": []})
            existing_code = set(rule_ctx["code_context"])
            existing_summary = set(rule_ctx["summary_context"])

            # Process code results with three-tier prioritization
            code_docs = code_results.get("documents", [[]])[0]
            code_metas = code_results.get("metadatas", [[]])[0]

            source_file_code, directory_code, fallback_code = [], [], []
            for doc, meta in zip(code_docs, code_metas):
                file_path = self._normalize_path(meta.get("file", ""))
                formatted = self._format_code_result(doc, meta, source_directory)
                if self._is_from_source_file(file_path, source_file_paths):
                    source_file_code.append(formatted)
                elif self._is_in_directory(file_path, source_directory):
                    directory_code.append(formatted)
                else:
                    fallback_code.append(formatted)

            # Process summary results with three-tier prioritization
            summary_docs = summary_results.get("documents", [[]])[0]
            summary_metas = summary_results.get("metadatas", [[]])[0]

            source_file_summary, directory_summary, fallback_summary = [], [], []
            for doc, meta in zip(summary_docs, summary_metas):
                summary_path = self._normalize_path(meta.get("path", ""))
                formatted = self._format_summary_result(doc, meta, source_directory)
                if self._is_from_source_file(summary_path, source_file_paths):
                    source_file_summary.append(formatted)
                elif self._is_in_directory(summary_path, source_directory):
                    directory_summary.append(formatted)
                else:
                    fallback_summary.append(formatted)

            # Append new results (prioritized order, no duplicates)
            new_code = list(rule_ctx["code_context"])
            for item in source_file_code + directory_code + fallback_code:
                if item not in existing_code:
                    new_code.append(item)

            new_summary = list(rule_ctx["summary_context"])
            for item in source_file_summary + directory_summary + fallback_summary:
                if item not in existing_summary:
                    new_summary.append(item)

            updated_contexts[rule_key] = {"code_context": new_code, "summary_context": new_summary}

        return {
            "rule_contexts": updated_contexts,
        }

    def test_generator_node(self, state: UTGraphState) -> UTGraphState:
        """
        @brief Generates unit tests for validated business rules.

        @details
        Uses the same language model but structured output to produce a unit test string
        for each rule that passed validation. The results are written to `unit_tests`
        in the workflow state for the final writer node.
        """
        validated_rules = state.get("validated_rules", [])
        if not validated_rules:
            return {"unit_tests": []}

        rule_contexts = state.get("rule_contexts", {})
        structured_llm = self.llm.with_structured_output(UnitTest)

        async def run_batch():
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            async def guarded(rule: ValidatedRule):
                async with sem:
                    ctx = rule_contexts.get(str(rule.id), {"code_context": [], "summary_context": []})
                    return await _generate_single_test(structured_llm, rule, ctx["code_context"], ctx["summary_context"])
            return await asyncio.gather(*(guarded(r) for r in validated_rules))

        results = self._loop.run_until_complete(run_batch())

        unit_tests = []
        for rule, output, err in results:
            if err is not None:
                print(f"Unit test generation error for rule {rule.id}: {err}")
                continue
            unit_tests.append(UnitTest(unit_test=output.unit_test, id=rule.id, rule=rule.rule))

        return {"unit_tests": unit_tests}

    def writer_node(self, state: UTGraphState) -> UTGraphState:
        """
        @brief Writes unit tests to JSON output files.

        @details
        Serializes unit tests from the workflow state to JSON files in an output directory named
        under {output_directory}/{codebase_name}/. Creates directories if needed.
        Runs exactly once at the end of the graph.

        @param state Current workflow state containing validated_rules.
        @return Empty dict (terminal node).
        """
        base_output_dir = state.get("output_directory", "./agent/UT_agent_output")
        codebase_subdir = os.path.join(base_output_dir, state["codebase_name"])
        os.makedirs(codebase_subdir, exist_ok=True)

        unit_tests = state.get("unit_tests", [])
        if unit_tests:
            unit_tests_path_json = os.path.join(codebase_subdir, "unit_tests.json")
            unit_tests_path_txt = os.path.join(codebase_subdir, "unit_tests.txt")
            with open(unit_tests_path_json, "w", encoding="utf-8") as f:
                json.dump([u.model_dump() for u in unit_tests], f, indent=2)
            with open(unit_tests_path_txt, "w", encoding="utf-8") as file:
                for test in unit_tests:
                    file.write(test.unit_test + "\n\n")
            print(f"Wrote {len(unit_tests)} unit tests to {unit_tests_path_json} and {unit_tests_path_txt}")
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

async def _generate_single_test(
    structured_llm,
    rule: ValidatedRule,
    code_context: list[str],
    summary_context: list[str],
) -> tuple:
    try:
        code_text = "\n\n".join(code_context) if code_context else "NO CONTEXT PROVIDED"
        summary_text = "\n\n".join(summary_context) if summary_context else "NO CONTEXT PROVIDED"

        system_message = (
            "You are a Senior Software Architect and expert Automated Test Engineer. "
            "Your sole objective is to output a syntactically flawless, concrete unit test method based "
            "strictly on an extracted business rule and the corresponding codebase architecture contexts provided."
        )

        prompt = f"""
#### BUSINESS RULE TO TEST:
- ID: {rule.id}
- RULE STATEMENT: {rule.rule}
- TARGET DIRECTORY: {rule.source_directory}
- EXPLANATION FOR VALIDATION: {rule.explanation}

#### RETRIEVED SOURCE CODE CONTEXT:
{code_text}

#### RETRIEVED FILE SUMMARY CONTEXT:
{summary_text}

### [REQUIRED TASK]
---
1. Analyze the provided Source Code and File Summaries to locate how the business rule is systematically enforced.
2. Generate exactly one realistic, structurally sound, executable unit test method.
3. Match the exact programming language, naming conventions, and testing framework patterns visible in the provided contexts (e.g., xUnit, NUnit, pytest).

### [STRICT EXECUTION CONSTRAINTS - DO NOT VIOLATE]
---
- **NO IMPORTS:** Do not emit any `import`, `using`, or package references. Output *only* the test method block.
- **NO DUPLICATION:** Create a completely unique method name that describes this rule. Do not copy an existing test title.
- **NO INVENTIONS:** Do not hallucinate or invent helper classes, mock interfaces, or functions that are absent from the provided context. Use the exact signatures present.
- **NO TEXT EXTRACTION:** The test must contain functioning assertions that exercise the rule logic—do not just repeat the text of the rule in a comment or string.
- **FORMATTING:** Use standard Unix line breaks (\\n) and canonical indentation to format the generated method code perfectly. 

*Note: If context is scarce, construct the most precise, narrow unit test possible based purely on the available evidence without making external assumptions or inventing anything.*
"""

        messages = [("system", system_message), ("user", prompt)]
        output = await structured_llm.ainvoke(messages)
        return rule, output, None
    except Exception as e:
        return rule, None, e

if __name__ == "__main__":
    """
    @brief Script entry point for running BRAgent.
    @details Loads business rules from a JSON file and runs the validation pipeline.
    """
    if len(sys.argv) != 3:
        print("Usage: python -m agent.BR_agent <codebase_path> <rules_json_path>")
        sys.exit(1)

    codebase = sys.argv[1]
    codebase_name = os.path.basename(codebase)
    rules_path = sys.argv[2]

    with open(rules_path, "r", encoding="utf-8") as f:
        raw_rules = json.load(f)

    # Convert raw JSON dicts back to BusinessRule objects
    input_rules = [ValidatedRule.model_validate(rule) for rule in raw_rules]   

    agent = UTAgent()
    agent.run(input_rules, codebase_name, codebase)
    print("UTAgent has completed its task!")
