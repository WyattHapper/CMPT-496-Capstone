"""
@file UT_agent_state.py
@brief Defines the shared state structure used by the UT Agent (G3) workflow.
@details This module defines the UTGraphState TypedDict, which represents the
structured state passed between nodes in the LangGraph execution graph.
"""

from typing import TypedDict, Annotated, Any
from agent.structured_output.UT_output import ValidatedRule, UnitTest
from operator import add


class UTGraphState(TypedDict):
    """
    @brief Represents the shared state passed between nodes in the UT Agent workflow graph.

    @var validated_rules
        Accumulating list of rules that passed validation with supporting evidence.
        Uses an additive reducer so each validator invocation appends without
        overwriting previous results.

    @var unit_tests
        Accumulating list of unit tests generated for validated rules.
        Uses an additive reducer so each test generator invocation appends
        without overwriting previous results.

    @var rule_contexts
        Per-rule retrieval context keyed by rule ID. Each value is a dict with
        "code_context" (list[str]) and "summary_context" (list[str]).
        Populated by the retriever node.
        Accumulates across retrieval iterations for the same rule.

    @var codebase_k
        Number of code snippets to retrieve from the code vector database per
        query iteration. Increased by the validator on "need_more_context"
        decisions. Reset when all rules are resolved.

    @var file_summary_k
        Number of summary entries to retrieve from the summary vector database
        per query iteration. Increased by the validator on "need_more_context"
        decisions. Reset when all rules are resolved.

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
        ./agent/UT_agent_output if not specified.
    """
    validated_rules: dict[str, list[ValidatedRule]]
    unit_tests: list[UnitTest]
    rule_contexts: dict[int, dict]
    test_path: str
    codebase_k: int
    file_summary_k: int
    code_collection: Any
    summary_collection: Any
    codebase_name: str
    codebase_path: str
    output_directory: str
