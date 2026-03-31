"""
@file BR_agent_state.py
@brief Defines the shared state structure used by the BR Agent (G3) workflow.
@details This module defines the BRGraphState TypedDict, which represents the
structured state passed between nodes in the LangGraph execution graph.
"""

from typing import TypedDict, Deque, Annotated, Any
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

    @var rules_queue
        Deque of condensed rules remaining to be validated. Populated by the
        condenser node and consumed one at a time by the retriever/validator loop.
        Rules are popped from the left.

    @var current_rule
        The condensed rule currently being retrieved for and validated. Set by
        the condenser (first rule) and by the validator (subsequent rules).
        Set to None when no rules remain, which triggers the writer node.

    @var validated_rules
        Accumulating list of rules that passed validation with supporting evidence.
        Uses an additive reducer so each validator invocation appends without
        overwriting previous results.

    @var discarded_rules
        Accumulating list of rules that were rejected during validation, along
        with the reason for rejection. Uses an additive reducer.

    @var code_context
        Retrieved code snippets relevant to the current rule. Accumulates across
        retrieval iterations for the same rule. Reset by the validator when
        advancing to the next rule.

    @var summary_context
        Retrieved file summaries relevant to the current rule. Accumulates across
        retrieval iterations for the same rule. Reset by the validator when
        advancing to the next rule.

    @var codebase_k
        Number of code snippets to retrieve from the code vector database per
        query iteration. Increased by the validator on "need_more_context"
        decisions. Reset when advancing to the next rule.

    @var file_summary_k
        Number of summary entries to retrieve from the summary vector database
        per query iteration. Increased by the validator on "need_more_context"
        decisions. Reset when advancing to the next rule.

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
    rules_queue: Deque[CondensedRule]
    current_rule: CondensedRule
    validated_rules: Annotated[list[ValidatedRule], add]
    discarded_rules: Annotated[list[DiscardedRule], add]
    code_context: list[str]
    summary_context: list[str]
    codebase_k: int
    file_summary_k: int
    code_collection: Any
    summary_collection: Any
    codebase_name: str
    output_directory: str
