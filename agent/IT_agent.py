"""
@file IT_agent.py
@brief Defines the ITAgent, a LangGraph-based agent for generating Integration Tests based of business rules.
@details Implements a retriever-generator-writer workflow that takes validated business rules from BR_agent output,
generates integration tests and writes the results to JSON.
"""
import logging
logger = logging.getLogger(__name__)
from agent.states.IT_agent_state import ITGraphState
from agent.structured_output.IT_output import (
    ValidatedRule, IntegrationTest, WorkflowGroup, WorkflowGroups
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
DEFAULT_CODEBASE_K = 30
DEFAULT_FILE_SUMMARY_K = 15
MAX_CODEBASE_K = 30
MAX_FILE_SUMMARY_K = 10

class ITAgent:
    """
    @brief LangGraph-based agent for generating integration tests based on business rules.

    @details
    The ITAgent constructs and executes a LangGraph workflow that:
    - Retrieves file and summary context for validated business rules from BR_agent output.
    - Generates integration tests for each validated rule.
    - Writes the generated integration tests to JSON output files.
    """

    def __init__(self, model=None):
        """
        @brief Initializes the ITAgent with a specified language model.
        @param model An optional language model to use. If not provided, defaults to gemini-3-flash-preview.
        """
        progress("Intializing integration test agent...", 5)
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
        @brief Constructs the StateGraph that defines the ITAgent workflow.
        @return A compiled StateGraph object.

        @details
        Graph structure:
            retriever → test_generator → writer → END

        Conditional routing from condenser and validator:
            - If current_rules is non-empty → retriever
            - If current_rules is empty (all rules processed) → writer
        """

        builder = StateGraph(ITGraphState)

        builder.add_node("workflow_grouper", self.workflow_grouper_node)
        builder.add_node("retriever", self.retriever_node)
        builder.add_node("test_generator", self.test_generator_node)
        builder.add_node("writer", self.writer_node)
        builder.add_node("runner", self.runner_node)


        builder.set_entry_point("workflow_grouper")

        builder.add_edge("workflow_grouper", "retriever")
        builder.add_edge("retriever", "test_generator")
        builder.add_edge("test_generator", "writer")
        builder.add_edge("writer", "runner")
        builder.add_edge("runner", END)

        return builder.compile()

    def run(self, validated_rules: list[ValidatedRule], codebase_name: str, codebase_path: str):
        """
        @brief Executes the ITAgent workflow.
        @param input_rules Dictionary of validated business rules from BR_agent output. Keys are file or directory paths,
               values are lists of ValidatedRule objects.
        @param codebase_name Name of the target codebase, used to look up the correct ChromaDB collections.
        @return Final state of the graph after execution.
        """
        progress(
            "Running integration test generation pipeline...",
            10
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
            20
        )

        initial_state = {
            "validated_rules": validated_rules,
            "integration_tests": [],
            "workflow_contexts": {},
            "test_imports": set(),
            "codebase_k": DEFAULT_CODEBASE_K,
            "file_summary_k": DEFAULT_FILE_SUMMARY_K,
            "code_collection": code_collection,
            "summary_collection": summary_collection,
            "codebase_name": codebase_name,
            "codebase_path": codebase_path,
            "output_directory": "./agent/IT_agent_output",
        }

        self._loop = asyncio.new_event_loop()
        try:
            return self.graph.invoke(initial_state)
        finally:
            self._loop.close()
            self._loop = None

    def workflow_grouper_node(self, state: ITGraphState) -> ITGraphState:
        """
            @brief Groups validated business rules into business workflows.

            @details
            Uses the language model to analyze all validated business rules and identify
            groups of rules that participate in the same end-to-end business workflow.

            Each workflow represents a collection of related business rules that should
            be exercised together in a single integration test.

            @param state Current workflow state containing validated business rules.
            @return Updated state containing workflow_groups.
        """

        progress(
            "Grouping validated business rules into workflows...",
         25
        )

        validated_rules = state.get("validated_rules", [])
        if not validated_rules:
            raise ValueError("No validated business rules provided.")

        structured_llm = self.llm.with_structured_output(WorkflowGroups)
        rules_text = ""

        for rule in validated_rules:
            rules_text += f"""
            ----------------------------------------

            Rule ID:
            {rule.id}

            Business Rule:
            {rule.rule}

            Validation Explanation:
            {rule.explanation}

            Source Directory:
            {rule.source_directory}

            Source Files:
            {", ".join(rule.source_file_paths)}

            """

        system_message = (
                    "You are a Senior Software Architect specializing in software "
                    "architecture analysis and integration testing."
            )

        prompt = f"""
            You are given a collection of validated business rules extracted from a software system.

            Your task is to identify which business rules belong to the same end-to-end business workflow.

            A workflow is a sequence of related business operations that together accomplish a user or
            system goal.

            Examples of workflows include:

            • User Registration
                - Validate Email
                - Create User
                - Save User
                - Send Welcome

            • Order Checkout
                - Validate Shopping Cart
                - Reserve Inventory
                - Process Payment
                - Generate Receipt

            • Password Reset
                - Validate Account
                - Generate Reset Token
                - Send Reset Email
                - Update Password

            Guidelines:

            - Every workflow should contain business rules that interact with one another.
            - A business rule may belong to ONLY ONE workflow.
            - Do NOT invent new business rules.
            - Do NOT modify existing business rules.
            - Use the validation explanations, directories, and source files to determine
            which rules are likely part of the same workflow.
            - Prefer grouping rules that span multiple files or components.

            Your response will be parsed into the following schema:

            WorkflowGroups
            └── workflows[]
                ├── workflow_name
                ├── workflow_description
                └── rule_ids

            Do not output markdown, explanations, or JSON examples.
            Only populate the schema fields.

            For each workflow:

            - workflow_name:
            A concise business workflow name.

            - workflow_description:
            One or two sentences describing the overall purpose of the workflow.

            - rule_ids:
            A list of the integer IDs of the validated business rules that belong to this workflow.

            Important constraints:

            - Every validated business rule must appear in exactly one workflow.
            - Do not omit any rule IDs.
            - Do not duplicate rule IDs across workflows.
            - Do not invent new rule IDs.
            - Do not return business rule objects.
            - Return only the integer IDs corresponding to the validated rules provided below.
            - Use the exact field names:
                • workflow_name
                • workflow_description
                • rule_ids

            BUSINESS RULES

            {rules_text}
        """

        messages = [
            ("system", system_message),
            ("user", prompt),
        ]



        progress("LLM returned workflow grouping.")
        output = structured_llm.invoke(messages)
        progress("Structured output parsed successfully.")

        progress(f"Output type: {type(output)}")

        # Build lookup table from rule ID -> ValidatedRule
        rule_lookup = {
            rule.id: rule
            for rule in validated_rules
        }

        progress("Structured output parsed.", 26)

        workflow_groups = []

        progress(f"Found {len(output.workflows)} workflows.", 27)

        for i, workflow in enumerate(output.workflows):
            progress(f"Processing workflow {i+1}/{len(output.workflows)}", 27)

            grouped_rules = [
                rule
                for rule in validated_rules
                if rule.id in workflow.rule_ids
            ]

            progress(f"Matched {len(grouped_rules)} rules.", 28)

            workflow_groups.append(
                WorkflowGroup(
                    workflow_name=workflow.workflow_name,
                    workflow_description=workflow.workflow_description,
                    rules=grouped_rules
                )
            )

        progress("Finished workflow grouping.", 29)

        progress(
            f"Grouped {len(validated_rules)} business rules into "
            f"{len(workflow_groups)} workflows.",
            30
        )

        return {
            "workflow_groups": workflow_groups,
        }
            
    
    def retriever_node(self, state: ITGraphState) -> ITGraphState:
        """
        @brief Retrieves relevant code snippets and file summaries for each business workflow.

        @details
        Iterates over workflow groups and queries ChromaDB code and summary collections.
        Each workflow combines the context of all business rules it contains.

        Retrieval priority:
            1. Files directly referenced by workflow rules
            2. Files inside workflow directories
            3. Other relevant retrieved files

        Workflow context is stored in workflow_contexts[workflow_name].

        @param state Current workflow state containing workflow groups and retrieval parameters.
        @return Updated state with workflow_contexts populated.
        """

        progress(
            "Retrieving context for business workflows...",
            30
        )

        workflow_groups = state.get("workflow_groups", [])
        if not workflow_groups:
            raise ValueError("No workflow groups to retrieve context for.")


        validated_rules = state.get("validated_rules", [])
        if not validated_rules:
            raise ValueError("No validated rules available.")

        # Build lookup table:
        # rule_id -> ValidatedRule
        rule_lookup = {
            rule.id: rule
            for rule in validated_rules
        }


        code_collection = state["code_collection"]
        summary_collection = state["summary_collection"]
        code_k = state["codebase_k"]
        summary_k = state["file_summary_k"]
        existing_contexts = state.get("workflow_contexts", {})
        updated_contexts = dict(existing_contexts)


        for workflow in workflow_groups:

            # Resolve workflow rule IDs back into ValidatedRule objects
            workflow_rules = workflow.rules

            if not workflow_rules:
                continue

            source_directories = set()
            source_file_paths = []
            rule_descriptions = []

            for rule in workflow_rules:
                source_directories.add(rule.source_directory)
                source_file_paths.extend(rule.source_file_paths)
                rule_descriptions.append(rule.rule)


            source_directory = ", ".join(source_directories)


            query_text = f"""
            Workflow:
            {workflow.workflow_name}

            Workflow Description:
            {workflow.workflow_description}

            Business Rules:
            {chr(10).join(rule_descriptions)}

            Source Directories:
            {source_directory}
            """


            safe_code_k = min(
                code_k,
                code_collection.count()
            ) or 1

            safe_summary_k = min(
                summary_k,
                summary_collection.count()
            ) or 1


            code_results = code_collection.query(query_texts=[query_text],n_results=safe_code_k)
            summary_results = summary_collection.query(query_texts=[query_text],n_results=safe_summary_k)


            # Workflow-level context storage
            workflow_key = workflow.workflow_name


            workflow_ctx = updated_contexts.get(
                workflow_key,
                {
                    "code_context": [],
                    "summary_context": []
                }
            )

            existing_code = set(workflow_ctx["code_context"])
            existing_summary = set(workflow_ctx["summary_context"])

            # -------------------------
            # Process code results
            # -------------------------

            code_docs = code_results.get("documents",[[]])[0]

            code_metas = code_results.get("metadatas",[[]])[0]

            source_file_code = []
            directory_code = []
            fallback_code = []


            for doc, meta in zip(code_docs, code_metas):

                file_path = self._normalize_path(
                    meta.get("file", "")
                )

                formatted = self._format_code_result(
                    doc,
                    meta,
                    source_directory
                )


                if self._is_from_source_file(
                    file_path,
                    source_file_paths
                ):
                    source_file_code.append(formatted)


                elif self._is_in_directory(
                    file_path,
                    source_directory
                ):
                    directory_code.append(formatted)

                else:
                    fallback_code.append(formatted)

            # -------------------------
            # Process summary results
            # -------------------------
            summary_docs = summary_results.get(
                "documents",
                [[]]
            )[0]

            summary_metas = summary_results.get(
                "metadatas",
                [[]]
            )[0]

            source_file_summary = []
            directory_summary = []
            fallback_summary = []


            for doc, meta in zip(summary_docs, summary_metas):

                summary_path = self._normalize_path(
                    meta.get("path", "")
                )


                formatted = self._format_summary_result(
                    doc,
                    meta,
                    source_directory
                )


                if self._is_from_source_file(
                    summary_path,
                    source_file_paths
                ):
                    source_file_summary.append(formatted)
                elif self._is_in_directory(
                    summary_path,
                    source_directory
                ):
                    directory_summary.append(formatted)
                else:
                    fallback_summary.append(formatted)

            # -------------------------
            # Merge contexts
            # -------------------------

            new_code = list(
                workflow_ctx["code_context"]
            )

            for item in (
                source_file_code
                + directory_code
                + fallback_code
            ):
                if item not in existing_code:
                    new_code.append(item)

            new_summary = list(workflow_ctx["summary_context"])

            for item in (
                source_file_summary
                + directory_summary
                + fallback_summary
            ):
                if item not in existing_summary:
                    new_summary.append(item)

            updated_contexts[workflow_key] = {"code_context": new_code,"summary_context": new_summary}


        progress(
            "Workflow context retrieval complete.",
            50
        )


        return {
            "workflow_contexts": updated_contexts
        }
    
    
    def test_generator_node(self, state: ITGraphState) -> ITGraphState:
        """
        @brief Generates integration tests for validated business rules.

        @details
        Uses the same language model but structured output to produce a integration test string
        for each rule that passed validation. The results are written to `integration_tests`
        in the workflow state for the final writer node.
        """

        progress(
            "Generating integration tests from workflows...",
            60
        )

        workflow_groups = state.get("workflow_groups", [])
        if not workflow_groups:
            return {
                "integration_tests": [],
                "test_imports": set()
            }
        
        workflow_contexts = state.get("workflow_contexts", {})  
        
        structured_llm = self.llm.with_structured_output(IntegrationTest)

        async def run_batch():
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            async def guarded(workflow):
                async with sem:
                    ctx = workflow_contexts.get(workflow.workflow_name, {"code_context": [], "summary_context": []})
                    return await _generate_single_test(structured_llm, workflow, workflow.rules, ctx["code_context"], ctx["summary_context"])
            return await asyncio.gather(*(guarded(workflow) for workflow in workflow_groups))

        results = self._loop.run_until_complete(run_batch())

        progress(
            f"Generated {len(results)} integration test candidates.",
            80
        )

        test_imports = set()
        integration_tests = []
        for workflow, output, err in results:
            if err is not None:
                progress(f"Integration test generation error for workflow {workflow.workflow_name}: {err}")
                logger.error(f"Integration test generation error for workflow {workflow.workflow_name}: {err}")
                continue
            test_imports.update(output.imports)
            integration_tests.append(IntegrationTest(workflow_name=workflow.workflow_name,workflow_description=workflow.workflow_description,rule_ids=[rule.id for rule in workflow.rules],imports=output.imports,integration_test=output.integration_test))
        progress(
            f"Generated integration tests for {len(integration_tests)} workflows.",
            85
        )
        return {"integration_tests": integration_tests, "test_imports": test_imports}

    def writer_node(self, state: ITGraphState) -> ITGraphState:
        """
        @brief Writes integration tests to JSON output files.

        @details
        Serializes integration tests from the workflow state to JSON files in an output directory named
        under {output_directory}/{codebase_name}/. Creates directories if needed.
        Runs exactly once at the end of the graph.

        @param state Current workflow state containing validated_rules.
        @return Empty dict (terminal node).
        """
        progress(
            "Writing generated integration tests...",
            90
        )

        codebase_name = state["codebase_name"]
        base_output_dir = state.get("output_directory", "./agent/IT_agent_output")
        codebase_subdir = os.path.join(base_output_dir, codebase_name)
        os.makedirs(codebase_subdir, exist_ok=True)
        integration_tests = state.get("integration_tests", [])

        if integration_tests:

            integration_tests_path_json = os.path.join(codebase_subdir, "integration_tests.json")
            integration_tests_path_txt = os.path.join(codebase_subdir, "integration_tests.txt")

            with open(integration_tests_path_json, "w", encoding="utf-8") as f:
                json.dump([u.model_dump() for u in integration_tests], f, indent=2)

            with open(integration_tests_path_txt, "w", encoding="utf-8") as file:
                for test in integration_tests:

                    file.write(f"// Workflow: {test.workflow_name}\n")
                    file.write(f"// Description: {test.workflow_description}\n")
                    file.write(f"// Covered Business Rules: {test.rule_ids}\n\n")

                    # Write imports first
                    if getattr(test, "imports", None):
                        for imp in test.imports:
                            imp = imp.strip()

                            # Skip invalid imports
                            if not imp:
                                continue

                            # Add using automatically
                            if not imp.startswith("using "):
                                imp = f"using {imp}"

                            # Add semicolon automatically
                            if not imp.endswith(";"):
                                imp += ";"

                            file.write(imp + "\n")

                        file.write("\n")

                    # Write test method
                    file.write(
                        test.integration_test + "\n\n"
                    )
            progress(
                f"Wrote {len(integration_tests)} workflow integration tests to "
                f"{integration_tests_path_json} and {integration_tests_path_txt}",
                98
            )
        return {}

    def runner_node(self, state: ITGraphState) -> ITGraphState:
        """
        @brief Creates test framework in target codebase and runs it

        @details Takes the generated integration tests and applies them with a testing framework and generates a report based on its results

        @param state Current workflow state contain integration_tests
        @return Empty dict
        """
        codebase_path = state["codebase_path"]
        codebase_name  = state["codebase_name"]
        test_subdir = os.path.join(codebase_path, f"{codebase_name}.Tests")

        # Generate Xunit framework
        if not Path(test_subdir).is_dir():
            try:
                progress("Generating test framework", 98)
                subprocess.run(
                    ["dotnet", "new", "xunit", "-o", f"{test_subdir}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                with open(f"{test_subdir}/{codebase_name}.Tests.csproj", "r+", encoding="utf-8") as file:
                    lines = file.readlines()
                    lines.insert(-1, '<ItemGroup>\n<ProjectReference Include="..\\**\\*.csproj" Exclude="..\\**\\*.Tests.csproj" />\n</ItemGroup>\n\n')
                    file.seek(0)
                    file.writelines(lines)
            except Exception as e:
                logger.error(f"Error: {e}")
                progress("Error generating framework", 98)

        # Write generated tests to Xunit .cs file
        test_imports = state["test_imports"]
        integration_tests = state["integration_tests"]
        with open(f"{test_subdir}/IntegrationTest1.cs", "w", encoding="utf-8") as file:
            for import_statement in test_imports:
                file.write(import_statement + "\n")
            file.write(f"\nnamespace {codebase_name}.Tests;\n".replace("-", "_"))
            file.write("\npublic class Tests {\n")
            for test in integration_tests:
                file.write(test.integration_test + "\n\n")
            file.write("}")
        
        # Run generated tests and produce report
        base_output_dir = state.get("output_directory", "./agent/IT_agent_output")
        codebase_dir = os.path.join(base_output_dir, codebase_name)
        try:
            progress("Running generated tests", 99)
            subprocess.run(
                [
                    "dotnet",
                    "test",
                    f"{test_subdir}",
                    "--logger",
                    "html",
                    "--results-directory",
                    f"{codebase_dir}"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"Successfully ran tests and report generated to {codebase_dir}")
            progress(f"Successfully ran tests and report generated to {codebase_dir}", 100, True)
        except Exception as e:
            logger.error(e)
            progress("Error running tests!", 100, True)
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
    workflow,
    workflow_rules,
    code_context: list[str],
    summary_context: list[str],
) -> tuple:
    try:
        code_text = "\n\n".join(code_context) if code_context else "NO CONTEXT PROVIDED"
        summary_text = "\n\n".join(summary_context) if summary_context else "NO CONTEXT PROVIDED"


        workflow_rules_text = ""

        for rule in workflow_rules:
            workflow_rules_text += f"""
            ----------------------------------------

            Rule ID:
            {rule.id}

            Business Rule:
            {rule.rule}

            Validation Explanation:
            {rule.explanation}

            Source Directory:
            {rule.source_directory}

            Source Files:
            {", ".join(rule.source_file_paths)}

            """


        system_message = (
            "You are a Senior Software Architect and expert Automated Test Engineer. "
            "Your objective is to generate a syntactically flawless end-to-end integration "
            "test for a complete software workflow. "
            "The workflow may span multiple files, services, and components. "
            "Generate tests that verify the interaction between these components."
        )

        prompt = f"""
        ### WORKFLOW TO TEST

        Workflow Name:
        {workflow.workflow_name}

        Workflow Description:
        {workflow.workflow_description}


        ### BUSINESS RULES IN THIS WORKFLOW

        {workflow_rules_text}


        ### RETRIEVED SOURCE CODE CONTEXT

        {code_text}


        ### RETRIEVED FILE SUMMARY CONTEXT

        {summary_text}



        ### REQUIRED TASK

        1. Analyze the provided source code and file summaries.

        2. Determine how this workflow is implemented across the application.

        3. Generate exactly ONE executable integration test.

        4. The test must exercise the complete workflow from start to finish.

        5. The test should verify interaction between multiple components where possible.

        6. Use the application's real dependency injection and service architecture.

        7. Generate required C# namespace imports.

            The imports field must contain ONLY namespace names.

            Examples:
            - System
            - System.Collections.Generic
            - Xunit
            - ConsoleTables

            Rules:
            - Do NOT include the word "using".
            - Do NOT include semicolons.
            - Do NOT include file paths.
            - Do NOT include comments.
            - Do NOT include markdown.
            - Each entry must be a valid C# namespace.

        8. Match the target programming language and testing framework.



        ### STRICT CONSTRAINTS

        - Only use components found in the provided context.
        - Do not create separate tests for each business rule.
        - The output must represent one end-to-end workflow test.
        - The integration_test field must contain only the test method.
        - Imports must be returned separately.

        ### TYPE USAGE RULES



        When creating test data:

        - Prefer using existing application classes, models, DTOs, and entities found in the retrieved source context.
        - Before instantiating any custom class, verify that the class definition exists in the provided context.
        - Do not create fake domain objects that are not present in the source code.
        - Do not assume properties, constructors, or methods exist.
        - If a required type cannot be found, use the simplest valid input supported by the existing API.
        - Framework types such as List<T>, Dictionary<TKey,TValue>, DataTable, StringWriter, etc. may be used normally.

        If a required object/class does not exist in retrieved context:
        - Create test data using primitive types already supported by the API.
        - Never invent domain models.
        """

        messages = [("system", system_message), ("user", prompt)]
        output = await structured_llm.ainvoke(messages)
        return workflow, output, None
    except Exception as e:
        return workflow, None, e

if __name__ == "__main__":
    """
    @brief Script entry point for running BRAgent.
    @details Loads business rules from a JSON file and runs the validation pipeline.
    """
    if len(sys.argv) != 3:
        progress("Usage: python -m agent.BR_agent <codebase_path> <rules_json_path>")
        sys.exit(1)

    codebase = sys.argv[1]
    codebase_name = os.path.basename(codebase)
    rules_path = sys.argv[2]

    with open(rules_path, "r", encoding="utf-8") as f:
        raw_rules = json.load(f)

    # Convert raw JSON dicts back to BusinessRule objects
    input_rules = [ValidatedRule.model_validate(rule) for rule in raw_rules]   

    agent = ITAgent()
    agent.run(input_rules, codebase_name, codebase)
    progress("ITAgent has completed its task!", 100, True)
