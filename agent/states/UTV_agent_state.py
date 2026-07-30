"""
@file UTV_agent_state.py
@brief Defines the shared state structure used by the UTV Agent (G3) workflow.
@details This module defines the UTVGraphState TypedDict, which represents the
structured state passed between nodes in the LangGraph execution graph.
"""

from typing import TypedDict, Annotated, Any
from agent.structured_output.UTV_output import UnitTest, Report
from operator import add


class UTVGraphState(TypedDict):
    """
    @brief Represents the shared state passed between nodes in the UT Agent workflow graph.

    @var current_tests
        The list of UnitTest candidates that are currently being validated.
        These tests are passed from the runner node into the validator node.

    @var validated_tests
        Accumulating list of UnitTest objects that the validator has marked as successful.
        These tests will be written to validated_tests.json.

    @var discarded_tests
        Accumulating list of UnitTest objects that the validator has rejected.
        These tests will be written to discarded_tests.json.

    @var report
        The most recent execution report returned by the runner node.
        This includes return_code, output, and errors from dotnet test.

    @var codebase_k
        Number of code snippets to retrieve from the code vector database per query iteration.
        Used when validation requires additional context.

    @var file_summary_k
        Number of summary entries to retrieve from the summary vector database per query iteration.
        Used when validation requires additional context.

    @var code_collection
        ChromaDB collection handle for embedded code snippets.

    @var summary_collection
        ChromaDB collection handle for embedded file/class/function summaries.

    @var codebase_name
        Name of the target codebase being analyzed, used for vector store
        lookup and output directory naming.

    @var codebase_path
        Path to the target codebase being analyzed, used for unit test file generation.

    @var output_directory
        Base directory for writing output JSON files. Defaults to
        ./agent/UTV_agent_output if not specified.
    """
    current_tests: list[UnitTest]
    validated_tests: Annotated[list[UnitTest], add]
    discarded_tests: Annotated[list[UnitTest], add]
    imports: set
    report: Report
    codebase_k: int
    file_summary_k: int
    code_collection: Any
    summary_collection: Any
    codebase_name: str
    codebase_path: str
    output_directory: str
