"""
@file UTV_agent.py
@brief Defines the UTVAgent, a LangGraph-based agent for validating generated unit tests from business rules.
@details Implements a runner-validator-writer workflow that:
- Writes candidate xUnit tests into the Test folder in the selected codebase project
- Executes them with `dotnet test`
- Validates the execution report using a structured LLM
- Separates validated tests from discarded tests and writes both to JSON output
- Generates html report based off new and improved tests
"""
import logging
logger = logging.getLogger(__name__)
from agent.states.UTV_agent_state import UTVGraphState
from agent.structured_output.UTV_output import (
    UnitTest, ValidatorOutput, Report
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

from agent.testing.runners.registry import RunnerRegistry

MAX_CONCURRENCY = 10
DEFAULT_CODEBASE_K = 15
DEFAULT_FILE_SUMMARY_K = 5
MAX_CODEBASE_K = 30
MAX_FILE_SUMMARY_K = 10
MAX_LLM_RETRIES = 4
LLM_RETRY_BACKOFF_SECONDS = 2


class UTVAgent:
    """
    @brief LangGraph-based agent for generating unit tests based on business rules.

    @details
    The UTVAgent constructs and executes a LangGraph workflow that:
    - Writes candidate xUnit tests into the selected codebase test project
    - Executes those tests with `dotnet test`
    - Validates the execution report using a structured LLM
    - Writes validated and discarded test metadata to JSON output files
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
            runner → validator → writer → END

        Conditional routing:
            - If the latest test execution report indicates failure → validator
            - If no further current tests remain after validation → writer
        """

        builder = StateGraph(UTVGraphState)

        # Set nodes
        builder.add_node("runner", self.runner_node)
        builder.add_node("validator", self.validator_node)
        builder.add_node("writer", self.writer_node)
        
        # Set edges
        builder.set_entry_point("runner")
        builder.add_conditional_edges(
            "runner",
            lambda state: "validator" if (state["report"].return_code != 0) else "writer"
        )
        builder.add_conditional_edges(
            "validator",
            lambda state: "runner" if state.get("current_tests") else "writer"
        )
        builder.add_edge("writer", END)
        return builder.compile()

    def run(self, input_tests: dict[str, list[UnitTest]], codebase_name: str, codebase_path: str):
        """
        @brief Executes the UTAgent workflow.
        @param input_tests Dictionary of unit test candidates keyed by source path.
               values are lists of UnitTest objects.
        @param codebase_name Name of the target codebase, used to look up the correct ChromaDB collections.
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

        imports = set()
        for test in input_tests:
            imports.update(test.imports)

        progress(
            "Loaded code and summary databases.",
            10
        )

        initial_state = {
            "current_tests": input_tests,
            "validated_tests": [],
            "discarded_tests": [],
            "imports": imports,
            "report": Report(return_code=1, output="", errors =""),
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

    def runner_node(self, state: UTVGraphState) -> UTVGraphState:
        """
        @brief Creates test framework in target codebase and runs it

        @details Takes the generated unit tests and applies them with a testing framework and generates a report based on its results

        @param state Current workflow state contain unit_tests
        @return Empty dict
        """
        
        progress("Writing and running generated tests for validation...", 40)
        
        #intialize the state
        runner_state = {
            "codebase_path": state["codebase_path"],
            "codebase_name": state["codebase_name"],
            "output_directory": state.get("output_directory", ".agent/UTV_agent_output"),
            "unit_tests": state["current_tests"]
        }

        #detect language to find the correct runner
        language = RunnerRegistry.detect_language(runner_state)

        if language is None:
            raise ValueError(
                f"Could not detect language for codebase: "
                f"{runner_state['codebase_path']}"
            )
        runner = RunnerRegistry.create_runner(language)

        runner_state = runner.run(runner_state)
        
        result = runner_state["test_result"]

        report = Report(
            return_code=(
                result["returncode"]
                if result["returncode"] is not None
                else 1
            ),
            output=result.get("stdout", ""),
            errors=result.get("stderr", "")
        )

        progress("Test Execution reports generated...", 43)
        return {"report": report}

        


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
            50
        )
        current_tests = state["current_tests"]
        if not current_tests:
            return {"validated_tests": []}
        codebase_k = state["codebase_k"]
        is_final_pass = codebase_k >= MAX_CODEBASE_K

        # rule_contexts = state.get("rule_contexts", {})
        structured_llm = self.llm.with_structured_output(ValidatorOutput)

        async def run_batch():
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            async def guarded(test: UnitTest):
                async with sem:
                    report = state["report"]
                    return await _validate_single_test(
                        structured_llm,
                        test,
                        report,
                    )
            return await asyncio.gather(*(guarded(r) for r in current_tests))

        results = self._loop.run_until_complete(run_batch())

        progress(
            f"Validated {len(results)} unit test candidates.",
            50
        )
               
        validated_tests = []
        discarded_tests = []
        current_tests = []
        imports = state["imports"]
        for test, output, err in results:
            if err is not None:
                progress(f"Unit test validation error for unit test {test.id}: {err}", 50)
                discarded_tests.append(UnitTest(
                    id=test.id,
                    rule=test.rule,
                    imports=test.imports,
                    source_directory=test.source_directory,
                    source_file_paths=test.source_file_paths,
                    unit_test=test.unit_test,
                ))
                continue
            if output.decision == "success":
                validated_tests.append(UnitTest(
                    id=test.id,
                    rule=test.rule,
                    imports=test.imports,
                    source_directory=test.source_directory,
                    source_file_paths=test.source_file_paths,
                    unit_test=test.unit_test,
                ))
                imports.update(test.imports)
            elif output.decision == "failure":
                if is_final_pass:
                    discarded_tests.append(UnitTest(
                        id=test.id,
                        rule=test.rule,
                        imports=output.imports,
                        source_directory=test.source_directory,
                        source_file_paths=test.source_file_paths,
                        unit_test=output.unit_test,
                    ))
                else:
                    current_tests.append(UnitTest(
                        id=test.id,
                        rule=test.rule,
                        imports=output.imports,
                        source_directory=test.source_directory,
                        source_file_paths=test.source_file_paths,
                        unit_test=output.unit_test,
                    ))

        progress(
            f"Validation pass complete: {len(validated_tests)} valid, {len(discarded_tests)} discarded",
            60
        )

        update: dict = {
            "validated_tests": validated_tests,
            "discarded_tests": discarded_tests,
            "imports": imports,
        }

        if current_tests:
            update["current_tests"] = current_tests
            update["codebase_k"] = MAX_CODEBASE_K
            update["file_summary_k"] = MAX_FILE_SUMMARY_K
        else:
            update["current_tests"] = []
            update["codebase_k"] = DEFAULT_CODEBASE_K
            update["file_summary_k"] = DEFAULT_FILE_SUMMARY_K

        return update

    def writer_node(self, state: UTVGraphState) -> UTVGraphState:
       
        """
        @brief Writes the validated and discarded unit tests to output files.

        @details Saves the final validation results as JSON and human-readable
        text files without depending on a particular testing framework.

        @param state Current workflow state containing validated_tests,
                    discarded_tests, codebase_name, and output_directory.
        @return An empty state update after writing the output files.
        """
       
        progress("Writing validation results... ", 90)

        try:
            output_dir = (Path(state.get("output_directory", ".agent/UTV_agent_output")) / state["codebase_name"])

            output_dir.mkdir(parents=True, exist_ok="True")

            validated_tests = sorted(
                state.get("validated_tests", []),
                key=lambda test : test.id
            )

            discarded_tests = sorted(
                state.get("discarded_tests", []),
                key=lambda test : test.id
            )

            #save results
            validated_path = output_dir / "validated_tests.json"    
            discarded_path = output_dir / "discarded_tests.json"    
           
            with validated_path.open("w", encoding="utf-8") as file:
                json.dump([test.model_dump() for test in validated_tests], file, indent=4)

            with validated_path.open("w", encoding="utf-8") as file:
               json.dump([test.model_dump() for test in validated_tests], file, indent=4)

            # save report as txt
            report_path = output_dir / "validation_resutls.txt"  

            with report_path.open("w", encoding="utf-8") as file:
                file.write("UNIT TEST VALIDATION RESULTS\n")
                file.write("=" * 32+"\n\n")
                
                file.write(f"Validate Rules: {len(validated_tests)}\n")
                file.write(f"Discarded Rules: {len(discarded_tests)}\n\n")

                file.write("VALIDATED TESTS\n")
                file.write("-" * 32+"\n")

                for test in validated_tests:
                    file.write(f"\nTest ID: {test.id}\n")

                    if getattr(test, "imports", None):
                        file.write("Imports:\n")
                        for import_statement in test.imports:
                            file.write(f"   {import_statement}\n")

                    test_code = (
                        getattr(test, "unit_test", None)
                        or getattr(test, "test_code", None) or
                        ""
                    )

                    file.write(f"{test_code}\n")

                file.write("\n\nDISCARDED TESTS\n")
                file.write("-" * 32+"\n")

                for test in discarded_tests:
                    file.write(f"\nTest ID: {test.id}\n")

                    test_code = (
                        getattr(test, "unit_test", None)
                        or getattr(test, "test_code", None) or
                        ""
                    )

                    file.write(f"{test_code}\n")

            progress("Validation results written successfully", 100)

        except(OSError, KeyError, TypeError, AttributeError) as error:
           logger.exception(f"Failed to write validation results: {error}")
           raise
           

    
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

    def _write_tests(self, test_subdir: str,  codebase_name: str, imports: set, current_tests: list[UnitTest]):
        with open(f"{test_subdir}/UnitTest1.cs", "w", encoding="utf-8") as file:
            for import_statement in imports:
                file.write(import_statement + "\n")
            file.write(f"\nnamespace {codebase_name}.Tests;\n".replace("-", "_"))
            file.write("\npublic class Tests {\n")
            for test in current_tests:
                file.write(test.unit_test + "\n\n")
            file.write("}")
        return


async def _validate_single_test(
    structured_llm,
    test: UnitTest,
    report: Report,
) -> tuple:
    try:
        system_message = (
            "You are a senior software engineer acting as an "
            "automated unit test auditor. Evaluate generated tests "
            "using the execution report and the conventions of the "
            "target language and testing framework."
        )

        prompt = f"""
#### UNIT TEST TO VALIDATE:
- ID: {test.id}
- UNIT TEST: {test.unit_test}
- IMPORTS: {test.imports}

#### UNIT TEST OUTPUT
{report.output}

#### REPORT ERRORS:
{report.errors}

#### TASK:
Determine whether the unit test shown above has succeeded or failed based off of the given report generated. If the case of a failure rework the unit test and imports to solve the issue.

1. **success** — The unit test succeeded when executed and resulted in ZERO errors or failures. Select this option only when:
   - The unit tests method name does not appear anywhere in a failure context or stack trace.

2. **failure** — The unit test is NOT supported and failed during execution. Choose this only when:
   - The test contains syntax errors or invalid structure that would cause it to fail or crash when run.
   - The test is not a complete, concrete unit test method block that can be run directly.
   - The method name of the unit test appears under a `[FAIL]` section, stack trace, error message, or `Assert` failure in the report

#### IMPORTANT
- If the unit test is specifically stated in the error report as a failure. The decision MUST be 'failure'.

#### RESPONSE INSTRUCTIONS:
- If "success": select 'success' as your decision.
- If "failure": select 'failure' as your decision and populate the unit_test and imports with your updated test and imports that fix the failure.

#### TASK IN CASE OF FAILURE:
- If the test decision results in a failure then update the original unit test and/or imports in order to solve the error that is currently present
- The new test must be a realistic, structurally sound, executable unit test method.
- Match the exact programming language, naming conventions, and recommended testing framework for that language (Example: Xunit for C#).
- Use the context from the unit test report because it will tell you exactly what problems arise from the test and what needs to be fixed.

#### [STRICT EXECUTION CONSTRAINTS - DO NOT VIOLATE]:
- **IMPORT SYNTAX:** Do not add or remove any import statements. Only alter the preexisting statements in order to make it full, complete and with correct syntax in the target programming language. (Example: C# statement = using **import**;) (Example: JavaScript statement = import **import**;)
- **NO REINVENTING:** Do not generate a completely new test and imports completely from scratch. Simply reuse the old one and ONLY change whats needs to be changed in order to fix the error.
- **NO INVENTIONS:** Do not hallucinate or invent helper classes, mock interfaces, or functions that are absent from the report.
- **NO TEXT EXTRACTION:** The test must contain functioning assertions that exercise the rule logic—do not just repeat the text of the rule in a comment or string.
- **FORMATTING:** Use standard Unix line breaks (\\n) and canonical indentation to format the generated method code perfectly. Do not use (\\\\n)
- **NO DECISION CHANGING:** Once you have selected your decision and attempted to rewrite the prompt in a case of failure. DO NOT change your decision to success no matter what
"""

        messages = [("system", system_message), ("user", prompt)]
        for attempt in range(MAX_LLM_RETRIES):
            try:
                output = await structured_llm.ainvoke(messages)
                return test, output, None
            except Exception as e:
                if "503" in e and attempt < MAX_LLM_RETRIES - 1:
                    wait_seconds = LLM_RETRY_BACKOFF_SECONDS * (2 ** attempt)
                    await asyncio.sleep(wait_seconds)
                    continue
                return test, None, e
    except Exception as e:
        return test, None, e
    

