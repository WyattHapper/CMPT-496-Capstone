"""
@file BR_agent_state.py
@brief Defines the shared state structure used by the BR Agent (G3) workflow.
@details This module defines the BRGraphState TypedDict, which represents the
structured state passed between nodes in the LangGraph execution graph.
"""

from typing import TypedDict, Annotated, Any
from agent.structured_output.BR_output import CondensedRule, ValidatedRule, DiscardedRule
from agent.structured_output.file_summary_output import BusinessRule
from operator import add


class BRGraphState(TypedDict):
    """
    @brief Represents the shared state passed between nodes in the BR Agent workflow graph.

    @var input_rules
        Raw business rules from G1/G2. Dictionary keyed by file or directory path,
        with values being lists of BusinessRule objects. This is the unprocessed
        input to the graph, consumed only by the condenser node.

    @var current_rules
        List of condensed rules currently being processed. Populated by the
        condenser node with all condensed rules, then narrowed by the validator
        to only rules needing more context on subsequent passes. An empty list
        triggers the writer node via the conditional edge.

    @var validated_rules
        Accumulating list of rules that passed validation with supporting evidence.
        Uses an additive reducer so each validator invocation appends without
        overwriting previous results.

    @var discarded_rules
        Accumulating list of rules that were rejected during validation, along
        with the reason for rejection. Uses an additive reducer.

    @var rule_contexts
        Per-rule retrieval context keyed by rule ID. Each value is a dict with
        "code_context" (list[str]) and "summary_context" (list[str]).
        Populated by the retriever node and consumed by the validator.
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

    @var output_directory
        Base directory for writing output JSON files. Defaults to
        ./agent/BR_agent_output if not specified.
    """
    input_rules: dict[str, list[BusinessRule]]
    current_rules: list[CondensedRule]
    validated_rules: Annotated[list[ValidatedRule], add]
    discarded_rules: Annotated[list[DiscardedRule], add]
    rule_contexts: dict[int, dict]
    codebase_k: int
    file_summary_k: int
    code_collection: Any
    summary_collection: Any
    codebase_name: str
    output_directory: str
