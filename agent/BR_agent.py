"""
@file BR_agent.py
@brief Defines the BRAgent, a LangGraph-based agent for validating and citing business rules extracted from source code.
@details Implements a condenser-retriever-validator-writer workflow that takes business rules from G1/G2,
condenses duplicates, validates each rule against vector-retrieved code context, and writes the results to JSON.
"""

from agent.states.BR_agent_state import BRGraphState
from agent.structured_output.BR_output import (
    CondensedRule, ValidatedRule, DiscardedRule,
    CondenserOutput, ValidatorOutput, Explanation
)
from agent.structured_output.file_summary_output import BusinessRule
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import sys
import json
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pathlib import Path
from collections import deque


class BRAgent:
    """
    @brief LangGraph-based agent for validating business rules against codebase evidence.

    @details
    The BRAgent constructs and executes a LangGraph workflow that:
    - Condenses duplicate/similar business rules from G1/G2 output.
    - Iteratively retrieves relevant code snippets and file summaries per rule.
    - Validates each rule against retrieved context, producing evidence citations or discarding unsupported rules.
    - Writes validated and discarded rules to JSON output files.
    """

    def __init__(self, model=None):
        """
        @brief Initializes the BRAgent with a specified language model.
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
        @brief Constructs the StateGraph that defines the BRAgent workflow.
        @return A compiled StateGraph object.

        @details
        Graph structure:
            condenser → retriever → validator → conditional → writer → END

        Conditional routing from validator:
            - If current_rule is set (need_more_context, or next rule popped) → retriever
            - If current_rule is None (all rules processed) → writer
        """
        builder = StateGraph(BRGraphState)

        # Set nodes
        builder.add_node("condenser", self.condenser_node)
        builder.add_node("retriever", self.retriever_node)
        builder.add_node("validator", self.validator_node)
        builder.add_node("writer", self.writer_node)

        # Set edges
        builder.set_entry_point("condenser")
        builder.add_edge("condenser", "retriever")
        builder.add_edge("retriever", "validator")
        builder.add_conditional_edges(
            "validator",
            lambda state: "retriever" if state.get("current_rule") else "writer"
        )
        builder.add_edge("writer", END)

        return builder.compile()

    def run(self, input_rules: dict[str, list[BusinessRule]], codebase_name: str):
        """
        @brief Executes the BRAgent workflow.
        @param input_rules Dictionary of business rules from G1/G2. Keys are file or directory paths,
               values are lists of BusinessRule objects.
        @param codebase_name Name of the target codebase, used to look up the correct ChromaDB collections.
        @return Final state of the graph after execution.
        """
        script_dir = Path(__file__).parent.resolve()
        db_dir = (script_dir.parent / "vectorStores").resolve()

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
            "input_rules": input_rules,
            "rules_queue": deque(),
            "current_rule": None,
            "validated_rules": [],
            "discarded_rules": [],
            "code_context": [],
            "summary_context": [],
            "codebase_k": 10,
            "file_summary_k": 10,
            "code_collection": code_collection,
            "summary_collection": summary_collection,
            "codebase_name": codebase_name,
            "output_directory": "./agent/BR_agent_output",
        }

        return self.graph.invoke(initial_state)

    def condenser_node(self, state: BRGraphState) -> BRGraphState:
        """
        @brief Condenses duplicate or near-duplicate business rules from G1/G2 output.

        @details
        Implementation considerations:
        - Receives raw rules via state["input_rules"], a dict keyed by file/directory path.
        - Groups rules by directory. The directory should be derived from the file path keys
          (e.g., os.path.dirname(file_path) relative to the codebase root).
        - For each directory group, prompts the LLM (with CondenserOutput structured output) to
          identify and merge duplicate or near-duplicate rules into a single condensed statement.
        - Assigns sequential integer IDs to all condensed rules across all groups.
        - Wraps each condensed rule string into a CondensedRule object carrying the source_directory
          and the list of source_file_paths from which the group's rules originated.
        - Populates rules_queue with all CondensedRule objects and pops the first as current_rule.
        - The specific condensation strategy (single LLM call vs. embedding-based pre-clustering)
          is to be determined based on observed rule volumes from real G1/G2 output.
        - Runs exactly once at the start of the graph.

        @param state Current workflow state containing input_rules.
        @return Updated state with rules_queue, current_rule populated.
        """
        pass

    def retriever_node(self, state: BRGraphState) -> BRGraphState:
        """
        @brief Retrieves relevant code snippets and file summaries for the current rule.

        @details
        Implementation considerations:
        - Takes current_rule from state and queries both vector stores (code_collection and
          summary_collection).
        - The query should be composed from the rule text and the source_directory of the
          current rule. If source_file_paths are available, they can be used to bias or
          prioritize results from the rule's origin files.
        - Retrieval depth is controlled by codebase_k and file_summary_k, which may be
          increased by the validator on "need_more_context" decisions.
        - Retrieved results are appended to code_context and summary_context (accumulating
          across iterations for the same rule). Duplicates should be avoided.
        - Follows the same retrieval and formatting pattern as DirectoryAgent.retriever_node,
          but the query is constructed from business rule text rather than directory name.

        @param state Current workflow state containing current_rule and retrieval parameters.
        @return Updated state with code_context and summary_context populated/extended.
        """
        pass

    def validator_node(self, state: BRGraphState) -> BRGraphState:
        """
        @brief Assesses context sufficiency and validates the current business rule in a single LLM call.

        @details
        Implementation considerations:
        - This node combines the responsibilities of context analysis and rule validation,
          reducing the number of LLM calls per rule from two to one.
        - Uses ValidatorOutput structured output with a Literal["need_more_context", "valid", "discard"]
          decision field to force the LLM into one of three distinct outcomes.
        - Prompt engineering is critical: the model must understand that "need_more_context" is a
          legitimate and distinct outcome from "discard". The prompt should clearly differentiate:
            * "need_more_context": the retrieved context is insufficient to make a judgement, and
              more retrieval may help.
            * "valid": the rule is supported by evidence in the retrieved context.
            * "discard": the rule is not supported and additional retrieval is unlikely to help.

        On "need_more_context":
        - Increase codebase_k and file_summary_k (bounded by a maximum cap).
        - If k values have reached the cap, force a decision (valid or discard) — do not allow
          infinite retrieval loops.
        - Keep current_rule unchanged so the conditional edge routes back to the retriever.

        On "valid":
        - Create a ValidatedRule from the current CondensedRule and the LLM's Explanation.
        - Return it as a single-element list (the Annotated[list, add] reducer will append it).
        - Reset retrieval state: clear code_context, summary_context, reset codebase_k and
          file_summary_k to defaults.
        - Pop the next rule from rules_queue as current_rule, or set current_rule to None if
          the queue is empty (triggering the writer via the conditional edge).

        On "discard":
        - Create a DiscardedRule from the current CondensedRule and the LLM's discard_reason.
        - Return it as a single-element list (the Annotated[list, add] reducer will append it).
        - Reset retrieval state and advance to next rule, same as "valid".

        @param state Current workflow state containing current_rule, contexts, and retrieval params.
        @return Updated state reflecting the decision outcome.
        """
        pass

    def writer_node(self, state: BRGraphState) -> BRGraphState:
        """
        @brief Writes validated and discarded rules to JSON output files.

        @details
        Implementation considerations:
        - Serializes state["validated_rules"] to a JSON file containing all rules that
          passed validation along with their Explanation evidence.
        - Serializes state["discarded_rules"] to a separate JSON file for transparency
          and debugging, containing all rejected rules with reasons.
        - Output directory structure: {output_directory}/{codebase_name}/
          with files like validated_rules.json and discarded_rules.json.
        - Creates output directories if they don't exist.
        - Runs exactly once at the end of the graph.

        @param state Current workflow state containing validated_rules and discarded_rules.
        @return Empty dict (terminal node).
        """
        pass


if __name__ == "__main__":
    """
    @brief Script entry point for running BRAgent.
    @details Loads business rules from a JSON file and runs the validation pipeline.
    """
    if len(sys.argv) != 3:
        print("Usage: python -m agent.BR_agent <codebase_name> <rules_json_path>")
        sys.exit(1)

    codebase_name = sys.argv[1]
    rules_path = sys.argv[2]

    with open(rules_path, "r", encoding="utf-8") as f:
        raw_rules = json.load(f)

    # Convert raw JSON dicts back to BusinessRule objects
    input_rules = {
        path: [BusinessRule(**rule) for rule in rules]
        for path, rules in raw_rules.items()
    }

    agent = BRAgent()
    agent.run(input_rules, codebase_name)
    print("BRAgent has completed its task!")
