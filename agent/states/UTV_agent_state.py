"""
@file UTV_agent_state.py
@brief Defines the shared state structure used by the UTV Agent (G3) workflow.
@details This module defines the UTVGraphState TypedDict, which represents the
structured state passed between nodes in the LangGraph execution graph.
"""

from typing import TypedDict, Any
from agent.structured_output.UTV_output import UnitTest


class UTVGraphState(TypedDict):
    """
    @brief Represents the shared state passed between nodes in the UTV Agent workflow graph.

    @var current_tests
        The list of UnitTest candidates being validated, as loaded from unit_tests.json.

    @var test_run
        TestRun from agent/test_harness.py: which tests were kept, repaired, dropped,
        passed and failed. Set by the validator node, written out by the writer node.

    @var code_collection
        ChromaDB collection handle for embedded code snippets, used to give the AI the
        real API when it repairs a test. None if the codebase has no code database.

    @var codebase_name
        Name of the target codebase being analyzed, used for vector store
        lookup and output directory naming.

    @var codebase_path
        Path to the target codebase being analyzed, used for unit test file generation.

    @var output_directory
        Base directory for writing output JSON files. Defaults to
        ./agent/UT_agent_output if not specified, so the results show under
        "View unit tests".
    """
    current_tests: list[UnitTest]
    test_run: Any
    code_collection: Any
    codebase_name: str
    codebase_path: str
    output_directory: str
