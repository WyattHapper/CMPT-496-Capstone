"""
@file UT_agent.py
@brief Defines the UTAgent, a LangGraph-based agent for generating Unit Tests based of business rules.
@details Implements a retriever-generator-writer workflow that takes validated business rules from BR_agent output,
generates unit tests and writes the results to JSON.
"""
import logging
logger = logging.getLogger(__name__)
from agent.states.UTV_agent_state import UTVGraphState
from agent.structured_output.UTV_output import (
    UnitTest, ValidatedTest, DiscardedTest, ValidatorOutput
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
import subprocess
from backend.progress_logging import progress

MAX_CONCURRENCY = 10
DEFAULT_CODEBASE_K = 15
DEFAULT_FILE_SUMMARY_K = 5
MAX_CODEBASE_K = 30
MAX_FILE_SUMMARY_K = 10


class UTVAgent:
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
        progress("Intializing unit test validation agent...", 5)
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

        builder = StateGraph(UTVGraphState)

        # Set nodes
        builder.add_node("retriever", self.retriever_node)
        builder.add_node("validator", self.validator_node)
        builder.add_node("writer", self.writer_node)
        builder.add_node("runner", self.runner_node)

        # Set edges
        builder.set_entry_point("retriever")
        builder.add_edge("retriever", "validator")
        builder.add_conditional_edges(
            "validator",
            lambda state: "retriever" if state.get("current_tests") else "writer"
        )
        builder.add_edge("writer", "runner")
        builder.add_edge("runner", END)

        return builder.compile()

    def run(self, input_tests: dict[str, list[UnitTest]], codebase_name: str, codebase_path: str):
        """
        @brief Executes the UTAgent workflow.
        @param input_rules Dictionary of validated business rules from BR_agent output. Keys are file or directory paths,
               values are lists of ValidatedRule objects.
        @param codebase_name Name of the target codebase, used to look up the correct ChromaDB collections.
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

        progress(
            "Loaded code and summary databases.",
            10
        )

        initial_state = {
            "input_tests": input_tests,
            "current_tests": input_tests,
            "validated_tests": [],
            "discarded_tests": [],
            "imports": set(),
            "rule_contexts": {},
            "codebase_k": DEFAULT_CODEBASE_K,
            "file_summary_k": DEFAULT_FILE_SUMMARY_K,
            "code_collection": code_collection,
            "summary_collection": summary_collection,
            "codebase_name": codebase_name,
            "codebase_path": codebase_path,
            "output_directory": "./agent/UTV_agent_output",
        }

        self._loop = asyncio.new_event_loop()
        try:
            return self.graph.invoke(initial_state)
        finally:
            self._loop.close()
            self._loop = None
    
    def retriever_node(self, state: UTVGraphState) -> UTVGraphState:
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
        progress(
            "Retrieving context for validated business rules...",
            20
        )
        current_tests = state.get("current_tests", [])
        if not current_tests:
            raise ValueError("No unit tests to retrieve context for.")

        code_collection = state["code_collection"]
        summary_collection = state["summary_collection"]
        code_k = state["codebase_k"]
        summary_k = state["file_summary_k"]

        existing_contexts = state.get("rule_contexts", {})
        updated_contexts = dict(existing_contexts)

        for test in current_tests:
            source_directory = test.source_directory
            source_file_paths = test.source_file_paths
            query_text = f"{test.rule} {source_directory}"

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
            rule_key = str(test.id)
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

        progress(
            "Unit test context retrieval complete.",
            30
        )
        return {
            "rule_contexts": updated_contexts,
        }

    def validator_node(self, state: UTVGraphState) -> UTVGraphState:
        """
        @brief Validates unit tests for generated tests.

        @details
        Uses the same language model but structured output to validate a unit test string
        for each inputted test. The results are written to `validated_tests`
        in the workflow state for the final writer node.
        """

        progress(
            "Validating unit tests...",
            40
        )
        current_tests = state.get("current_tests", [])
        if not current_tests:
            return {"validated_tests": []}
        codebase_k = state["codebase_k"]
        is_final_pass = codebase_k >= MAX_CODEBASE_K

        rule_contexts = state.get("rule_contexts", {})
        structured_llm = self.llm.with_structured_output(ValidatorOutput)

        async def run_batch():
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            async def guarded(test: UnitTest):
                async with sem:
                    ctx = rule_contexts.get(str(test.id), {"code_context": [], "summary_context": []})
                    return await _validate_single_test(structured_llm, test, ctx["code_context"], ctx["summary_context"], is_final_pass)
            return await asyncio.gather(*(guarded(r) for r in current_tests))

        results = self._loop.run_until_complete(run_batch())

        progress(
            f"Validated {len(results)} unit test candidates.",
            50
        )
               
        validated_tests = []
        discarded_tests = []
        needs_context = []
        imports = set()
        for test, output, err in results:
            if err is not None:
                progress(f"Unit test validation error for unit test {test.id}: {err}")
                logger.error(f"Unit test validation error for unit test {test.id}: {err}")
                discarded_tests.append(DiscardedTest(
                    id=test.id,
                    rule=test.rule,
                    imports=test.imports,
                    source_directory=test.source_directory,
                    source_file_paths=test.source_file_paths,
                    unit_test=test.unit_test,
                    reason=f"Validation failed with error {err}"
                ))
                continue
            if output.decision == "valid":
                validated_tests.append(ValidatedTest(
                    id=test.id,
                    rule=test.rule,
                    imports=test.imports,
                    source_directory=test.source_directory,
                    source_file_paths=test.source_file_paths,
                    unit_test=test.unit_test,
                    explanation=output.explanation
                ))
                imports.update(test.imports)
            elif output.decision == "discard":
                discarded_tests.append(DiscardedTest(
                    id=test.id,
                    rule=test.rule,
                    imports=test.imports,
                    source_directory=test.source_directory,
                    source_file_paths=test.source_file_paths,
                    unit_test=test.unit_test,
                    reason=output.discard_reason
                ))
            elif output.decision == "need_more_context":
                if is_final_pass:
                    discarded_tests.append(DiscardedTest(
                        id=test.id,
                        rule=test.rule,
                        imports=test.imports,
                        source_directory=test.source_directory,
                        source_file_paths=test.source_file_paths,
                        unit_test=test.unit_test,
                        reason="Insufficient evidence after maximum context retrieval"
                    ))  
                else:
                    needs_context.append(test)

        progress(
            f"Validation pass complete: {len(validated_tests)} valid, "
                    f"{len(discarded_tests)} discarded, {len(needs_context)} need more context.",
            60
        )

        update: dict = {
            "validated_tests": validated_tests,
            "discarded_tests": discarded_tests,
            "imports": imports,
        }

        if needs_context:
            update["current_tests"] = needs_context
            update["codebase_k"] = MAX_CODEBASE_K
            update["file_summary_k"] = MAX_FILE_SUMMARY_K
            # Keep only contexts for unresolved rules
            update["rule_contexts"] = {str(r.id): rule_contexts.get(str(r.id), {"code_context": [], "summary_context": []})
                                       for r in needs_context}
        else:
            update["current_tests"] = []
            update["codebase_k"] = DEFAULT_CODEBASE_K
            update["file_summary_k"] = DEFAULT_FILE_SUMMARY_K
            update["rule_contexts"] = {}

        return update

    def writer_node(self, state: UTVGraphState) -> UTVGraphState:
        """
        @brief Writes unit tests to JSON output files.

        @details
        Serializes unit tests from the workflow state to JSON files in an output directory named
        under {output_directory}/{codebase_name}/. Creates directories if needed.
        Runs exactly once at the end of the graph.

        @param state Current workflow state containing validated_rules.
        @return Empty dict (terminal node).
        """
        progress(
            "Writing validated and discarded unit tests...",
            70
        )

        codebase_name = state["codebase_name"]
        base_output_dir = state.get("output_directory", "./agent/UTV_agent_output")
        codebase_subdir = os.path.join(base_output_dir, codebase_name)
        os.makedirs(codebase_subdir, exist_ok=True)
        validated_tests = state.get("validated_tests", [])
        discarded_tests = state.get("discarded_tests", [])
        if validated_tests:
            validated_tests_path = os.path.join(codebase_subdir, "validated_tests.json")
            discarded_tests_path = os.path.join(codebase_subdir, "discarded_tests.json")
            with open(validated_tests_path, "w", encoding="utf-8") as file:
                json.dump([test.model_dump() for test in validated_tests], file, indent=2)
            with open(discarded_tests_path, "w", encoding="utf-8") as file:
                json.dump([test.model_dump() for test in discarded_tests], file, indent=2)
            progress(f"Wrote {len(validated_tests)} validated unit tests to {validated_tests_path} and wrote {len(discarded_tests)} discarded unit tests to {discarded_tests_path}", 80)
        return {}

    def runner_node(self, state: UTVGraphState) -> UTVGraphState:
        """
        @brief Creates test framework in target codebase and runs it

        @details Takes the generated unit tests and applies them with a testing framework and generates a report based on its results

        @param state Current workflow state contain unit_tests
        @return Empty dict
        """
        codebase_path = state["codebase_path"]
        codebase_name  = state["codebase_name"]
        test_subdir = os.path.join(codebase_path, f"{codebase_name}.Tests")

        # Generate Xunit framework
        progress("Creating test framework...", 90)
        if not Path(test_subdir).is_dir():
            try:
                progress("Initializing xUnit project...", 95)
                subprocess.run(["dotnet", "new", "xunit", "-o", f"{test_subdir}"])
                progress("Configuring project references...", 95)
                with open(f"{test_subdir}/{codebase_name}.Tests.csproj", "r+", encoding="utf-8") as file:
                    lines = file.readlines()
                    lines.insert(-1, '<ItemGroup>\n<ProjectReference Include="..\\**\\*.csproj" Exclude="..\\**\\*.Tests.csproj" />\n</ItemGroup>\n\n')
                    file.seek(0)
                    file.writelines(lines)
            except Exception as e:
                logger.error(f"Error: {e}")
                progress(f"Error setting up test framework: {e}", 95, True)

        # Write generated tests to Xunit .cs file
        progress("Writing generated tests to file...", 97)
        imports = state["imports"]
        validated_tests = state["validated_tests"]
        with open(f"{test_subdir}/UnitTest1.cs", "w", encoding="utf-8") as file:
            for import_statement in imports:
                file.write(import_statement + "\n")
            file.write(f"\nnamespace {codebase_name}.Tests;\n".replace("-", "_"))
            file.write("\npublic class Tests {\n")
            for test in validated_tests:
                file.write(test.unit_test + "\n\n")
            file.write("}")
        
        # Run generated tests and produce report
        progress("Running unit tests (this may take a moment)...", 99)
        base_output_dir = state.get("output_directory", "./agent/UTV_agent_output")
        codebase_dir = os.path.join(base_output_dir, codebase_name)
        try:
            subprocess.run(["dotnet", "test", f"{test_subdir}", "--logger", "html", "--results-directory", f"{codebase_dir}"])
            logger.info(f"Successfully ran tests and report generated to {codebase_dir}")
            progress("Tests completed. Generating report...", 100, True)
        except Exception as e:
            logger.error(e)
            progress(f"Error running tests: {e}", 100, True)
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

async def _validate_single_test(
    structured_llm,
    test: UnitTest,
    code_context: list[str],
    summary_context: list[str],
    is_final_pass: bool
) -> tuple:
    try:
        code_text = "\n\n".join(code_context) if code_context else "NO CONTEXT PROVIDED"
        summary_text = "\n\n".join(summary_context) if summary_context else "NO CONTEXT PROVIDED"

        force_decision_clause = ""
        if is_final_pass:
            force_decision_clause = (
                "\nIMPORTANT: This is the final retrieval pass — maximum context has been gathered. "
                "\"need_more_context\" is NOT available as a decision. You MUST choose either \"valid\" or \"discard\"."
            )
    
        system_message = (
            "You are a Senior Software Architect acting as a unit test auditor. "
            "Your task is to determine whether a generated unit test is genuinely supported "
            "by the source code evidence provided. You must be precise and evidence-driven — "
            "never confirm a test based on assumptions."
        )

        prompt = f"""
#### UNIT TEST TO VALIDATE:
- ID: {test.id}
- ASSOCIATED BUSINESS RULE: {test.rule}
- UNIT TEST: {test.unit_test}
- TARGET DIRECTORY: {test.source_directory}
- SOURCE FILES: {", ".join(test.source_file_paths)}

#### RETRIEVED SOURCE CODE CONTEXT:
{code_text}

#### RETRIEVED FILE SUMMARY CONTEXT:
{summary_text}

WHAT IS A UNIT TEST:
A unit test is a small piece of automated code written to verify that a single, isolated part of an application—usually a function or method—behaves correctly.

TASK:
Determine whether the unit test shown above is supported by the retrieved code and summary context. Choose exactly one of three outcomes:

1. **valid** — The test IS supported by concrete evidence in the context. The test must be clearly runnable, match the codebase's language and framework, and be likely to produce a correct result when executed. You can point to specific code snippets, method signatures, validation checks, conditional logic, or summary statements that directly enforce or implement the test.

2. **discard** — The test is NOT supported, and additional retrieval is unlikely to help. Choose this when:
   - The context covers the relevant area thoroughly but shows no evidence of the test.
   - The test contradicts what the code actually does.
   - The test is too vague or generic to be grounded in any specific code behavior.
   - The test uses hallucinated methods, classes, or functions that aren't present in the context.
   - The test contains syntax errors, incorrect imports, missing dependencies, or invalid structure that would cause it to fail or crash when run.
   - The test would likely fail when executed, even if some parts appear plausible.
   - The test is not a complete, concrete unit test method block that can be run directly.

3. **need_more_context** — The context is insufficient to make a confident judgement. Choose this ONLY when:
   - The context contains partial hints (e.g., a method call to an unresolved external function) that suggest the test MIGHT be supported with more code.
   - The source directory or file area hasn't been well covered by retrieval yet.
   - Do NOT choose this as a "safe" fallback. If the context is reasonably thorough and shows no evidence, choose "discard".
{force_decision_clause}

HANDLING BORDERLINE / PARTIAL EVIDENCE:
- If the evidence only partially supports the test (e.g., the code enforces a narrower version of the stated constraint), choose "valid" but note the narrower scope in your reasoning.
- If the test is broadly stated but the code only demonstrates one specific case, validate the specific case you can confirm and explain the gap in your reasoning.
- If the code hints at the test but the logic is ambiguous or incomplete, prefer "need_more_context" over "valid" on the first pass.

RESPONSE INSTRUCTIONS:
- If "valid": populate the `explanation` field with `evidence` (a dict mapping filenames to lists of relevant code snippets that support the test) and `reasoning` (a clear explanation of how those snippets support the test).
- If "discard": populate the `discard_reason` field explaining why the test is not supported.
- If "need_more_context": leave both `explanation` and `discard_reason` as None.
"""

        messages = [("system", system_message), ("user", prompt)]
        output = await structured_llm.ainvoke(messages)
        return test, output, None
    except Exception as e:
        return test, None, e

