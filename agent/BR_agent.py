"""
@file BR_agent.py
@brief Defines the BRAgent, a LangGraph-based agent for validating and citing business rules extracted from source code.
@details Implements a condenser-retriever-validator-writer workflow that takes business rules from G1/G2,
condenses duplicates, validates each rule against vector-retrieved code context, and writes the results to JSON.
"""

from agent.states.BR_agent_state import BRGraphState
from agent.structured_output.BR_output import (
    CondensedRule, ValidatedRule, DiscardedRule,
    CondenserOutput, ValidatorOutput,
)
from agent.structured_output.file_summary_output import BusinessRule
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

        Conditional routing from condenser and validator:
            - If current_rules is non-empty → retriever
            - If current_rules is empty (all rules processed) → writer
        """
        builder = StateGraph(BRGraphState)

        # Set nodes
        builder.add_node("condenser", self.condenser_node)
        builder.add_node("retriever", self.retriever_node)
        builder.add_node("validator", self.validator_node)
        builder.add_node("writer", self.writer_node)

        # Set edges
        builder.set_entry_point("condenser")
        builder.add_conditional_edges(
            "condenser",
            lambda state: "retriever" if state.get("current_rules") else "writer"
        )
        builder.add_edge("retriever", "validator")
        builder.add_conditional_edges(
            "validator",
            lambda state: "retriever" if state.get("current_rules") else "writer"
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
            "current_rules": [],
            "validated_rules": [],
            "discarded_rules": [],
            "rule_contexts": {},
            "codebase_k": DEFAULT_CODEBASE_K,
            "file_summary_k": DEFAULT_FILE_SUMMARY_K,
            "code_collection": code_collection,
            "summary_collection": summary_collection,
            "codebase_name": codebase_name,
            "output_directory": "./agent/BR_agent_output",
        }

        self._loop = asyncio.new_event_loop()
        try:
            return self.graph.invoke(initial_state)
        finally:
            self._loop.close()
            self._loop = None

    def condenser_node(self, state: BRGraphState) -> BRGraphState:
        """
        @brief Condenses duplicate or near-duplicate business rules from G1/G2 output.

        @details
        Groups input rules by directory (derived from file path keys, made relative to codebase root).
        For each directory group with more than one rule, prompts the LLM (with CondenserOutput
        structured output) to identify and merge duplicates or near-duplicates.
        Single-rule groups are passed through without an LLM call.
        LLM calls are batched concurrently across directory groups for speed.
        IDs are assigned sequentially after all results are collected, in sorted directory order.
        Each CondensedRule carries all source file paths from its directory group.
        Runs exactly once at the start of the graph.

        @param state Current workflow state containing input_rules and codebase_name.
        @return Updated state with current_rules and rule_contexts populated.
        """
        input_rules = state["input_rules"]
        codebase_name = state["codebase_name"]

        # Handle empty input
        if not input_rules:
            return {
                "current_rules": [],
                "rule_contexts": {},
            }

        # Group rules by relative directory
        # Keys in input_rules are file paths; derive directory relative to codebase root
        dir_groups: dict[str, dict] = defaultdict(lambda: {"rules": [], "file_paths": set()})

        for file_path, rules in input_rules.items():
            abs_dir = os.path.dirname(file_path)

            # Attempt to make the directory relative to the codebase root
            # The codebase root name appears in the path; find it and compute relative
            try:
                path_obj = Path(abs_dir)
                # Walk up to find the codebase root directory
                parts = path_obj.parts
                codebase_idx = None
                for i, part in enumerate(parts):
                    if part == codebase_name:
                        codebase_idx = i
                        break

                if codebase_idx is not None:
                    rel_dir = Path(*parts[codebase_idx:]).as_posix()
                else:
                    rel_dir = Path(abs_dir).as_posix() if abs_dir else "."
            except (ValueError, TypeError):
                rel_dir = abs_dir if abs_dir else "."

            dir_groups[rel_dir]["file_paths"].add(file_path)
            dir_groups[rel_dir]["rules"].extend(rules)

        # Filter out groups with no rules
        dir_groups = {k: v for k, v in dir_groups.items() if v["rules"]}

        # Separate single-rule groups (no LLM call needed) from multi-rule groups
        single_rule_groups = {}
        multi_rule_groups = {}
        for dir_name, group in dir_groups.items():
            if len(group["rules"]) == 1:
                single_rule_groups[dir_name] = group
            else:
                multi_rule_groups[dir_name] = group

        # Batch async LLM calls for multi-rule groups
        structured_llm = self.llm.with_structured_output(CondenserOutput)
        sorted_multi_dirs = sorted(multi_rule_groups.keys())

        async def run_batch():
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            async def guarded(directory: str):
                async with sem:
                    return await _condense_group(
                        structured_llm,
                        directory,
                        multi_rule_groups[directory]["rules"]
                    )
            return await asyncio.gather(
                *(guarded(d) for d in sorted_multi_dirs)
            )

        if sorted_multi_dirs:
            results = self._loop.run_until_complete(run_batch())
        else:
            results = []

        # Build condensed rule results keyed by directory (preserving sorted order)
        # results[i] corresponds to sorted_multi_dirs[i]
        condensed_by_dir: dict[str, list[str]] = {}
        for dir_name, (returned_dir, condensed_strings, err) in zip(sorted_multi_dirs, results):
            if err is not None:
                # On error, pass through original rules uncondensed
                print(f"Condensation error for {dir_name}: {err}")
                condensed_strings = [r.rule for r in multi_rule_groups[dir_name]["rules"]]
            condensed_by_dir[dir_name] = condensed_strings

        # Assign sequential IDs across all groups in sorted directory order
        all_condensed: list[CondensedRule] = []
        rule_id = 1

        for dir_name in sorted(dir_groups.keys()):
            group = dir_groups[dir_name]
            file_paths = sorted(group["file_paths"])

            if dir_name in single_rule_groups:
                # Single rule — pass through without LLM
                rule_text = group["rules"][0].rule
                all_condensed.append(CondensedRule(
                    id=rule_id,
                    rule=rule_text,
                    source_directory=dir_name,
                    source_file_paths=file_paths,
                ))
                rule_id += 1
            else:
                # Multi-rule group — use LLM-condensed results
                for rule_text in condensed_by_dir[dir_name]:
                    all_condensed.append(CondensedRule(
                        id=rule_id,
                        rule=rule_text,
                        source_directory=dir_name,
                        source_file_paths=file_paths,
                    ))
                    rule_id += 1

        print(f"Condensed {sum(len(g['rules']) for g in dir_groups.values())} input rules "
              f"into {len(all_condensed)} condensed rules across {len(dir_groups)} directory groups.")

        return {
            "current_rules": all_condensed,
            "rule_contexts": {},
        }

    def retriever_node(self, state: BRGraphState) -> BRGraphState:
        """
        @brief Retrieves relevant code snippets and file summaries for all current business rules.

        @details
        Iterates over every rule in current_rules and queries two ChromaDB vector
        collections (code and summary) for each. Results are prioritized in three tiers:
            1. Results from the rule's source files (highest priority)
            2. Results from the rule's source directory
            3. All other results (fallback)

        Per-rule context is stored in rule_contexts[rule.id] and accumulates across
        retrieval iterations for the same rule (deduplication against prior results).
        Retrieval depth is controlled by codebase_k and file_summary_k, which may be
        increased by the validator on "need_more_context" decisions.

        @param state Current workflow state containing current_rules and retrieval parameters.
        @return Updated state with rule_contexts populated/extended.
        @raises ValueError If current_rules is empty.
        """
        current_rules = state.get("current_rules", [])
        if not current_rules:
            raise ValueError("No current rules to retrieve context for.")

        code_collection = state["code_collection"]
        summary_collection = state["summary_collection"]
        code_k = state["codebase_k"]
        summary_k = state["file_summary_k"]

        existing_contexts = state.get("rule_contexts", {})
        updated_contexts = dict(existing_contexts)

        for rule in current_rules:
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

    def validator_node(self, state: BRGraphState) -> BRGraphState:
        """
        @brief Validates all current business rules against retrieved context in batched async LLM calls.

        @details
        For each rule in current_rules, makes a single LLM call that assesses context
        sufficiency and rule validity simultaneously, using ValidatorOutput structured output.
        Calls are batched concurrently (up to MAX_CONCURRENCY) for speed.

        After all calls complete, results are partitioned:
        - "valid" → ValidatedRule appended to validated_rules
        - "discard" → DiscardedRule appended to discarded_rules
        - "need_more_context" → rule kept for a second retrieval pass at max k values

        If k values are already at their maximums (final pass), "need_more_context" is
        force-treated as a discard. This guarantees at most 2 LLM calls per rule.

        @param state Current workflow state containing current_rules, rule_contexts, and retrieval params.
        @return Updated state reflecting the decision outcomes for all rules.
        """
        current_rules = state.get("current_rules", [])
        rule_contexts = state.get("rule_contexts", {})
        codebase_k = state["codebase_k"]

        is_final_pass = codebase_k >= MAX_CODEBASE_K

        structured_llm = self.llm.with_structured_output(ValidatorOutput)

        async def run_batch():
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            async def guarded(rule: CondensedRule):
                async with sem:
                    ctx = rule_contexts.get(str(rule.id), {"code_context": [], "summary_context": []})
                    return await _validate_single_rule(
                        structured_llm,
                        rule,
                        ctx["code_context"],
                        ctx["summary_context"],
                        is_final_pass,
                    )
            return await asyncio.gather(
                *(guarded(r) for r in current_rules)
            )

        results = self._loop.run_until_complete(run_batch())

        new_validated = []
        new_discarded = []
        needs_context = []

        for rule, output, err in results:
            if err is not None:
                print(f"Validation error for rule {rule.id}: {err}")
                new_discarded.append(DiscardedRule(
                    id=rule.id,
                    rule=rule.rule,
                    source_directory=rule.source_directory,
                    reason=f"Validation failed with error: {err}",
                ))
                continue

            if output.decision == "valid":
                new_validated.append(ValidatedRule(
                    id=rule.id,
                    rule=rule.rule,
                    source_directory=rule.source_directory,
                    explanation=output.explanation,
                ))
            elif output.decision == "discard":
                new_discarded.append(DiscardedRule(
                    id=rule.id,
                    rule=rule.rule,
                    source_directory=rule.source_directory,
                    reason=output.discard_reason or "No reason provided.",
                ))
            elif output.decision == "need_more_context":
                if is_final_pass:
                    new_discarded.append(DiscardedRule(
                        id=rule.id,
                        rule=rule.rule,
                        source_directory=rule.source_directory,
                        reason="Insufficient evidence after maximum context retrieval.",
                    ))
                else:
                    needs_context.append(rule)

        print(f"Validation pass complete: {len(new_validated)} valid, "
              f"{len(new_discarded)} discarded, {len(needs_context)} need more context.")

        update: dict = {
            "validated_rules": new_validated,
            "discarded_rules": new_discarded,
        }

        if needs_context:
            update["current_rules"] = needs_context
            update["codebase_k"] = MAX_CODEBASE_K
            update["file_summary_k"] = MAX_FILE_SUMMARY_K
            # Keep only contexts for unresolved rules
            update["rule_contexts"] = {str(r.id): rule_contexts.get(str(r.id), {"code_context": [], "summary_context": []})
                                       for r in needs_context}
        else:
            update["current_rules"] = []
            update["codebase_k"] = DEFAULT_CODEBASE_K
            update["file_summary_k"] = DEFAULT_FILE_SUMMARY_K
            update["rule_contexts"] = {}

        return update

    def writer_node(self, state: BRGraphState) -> BRGraphState:
        """
        @brief Writes validated and discarded rules to JSON output files.

        @details
        Serializes validated_rules and discarded_rules to separate JSON files
        under {output_directory}/{codebase_name}/. Creates directories if needed.
        Runs exactly once at the end of the graph.

        @param state Current workflow state containing validated_rules and discarded_rules.
        @return Empty dict (terminal node).
        """
        base_output_dir = state.get("output_directory", "./agent/BR_agent_output")
        codebase_subdir = os.path.join(base_output_dir, state["codebase_name"])
        os.makedirs(codebase_subdir, exist_ok=True)

        validated = state.get("validated_rules", [])
        discarded = state.get("discarded_rules", [])

        validated_path = os.path.join(codebase_subdir, "validated_rules.json")
        with open(validated_path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump() for r in validated], f, indent=2)

        discarded_path = os.path.join(codebase_subdir, "discarded_rules.json")
        with open(discarded_path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump() for r in discarded], f, indent=2)

        print(f"Wrote {len(validated)} validated rules to {validated_path}")
        print(f"Wrote {len(discarded)} discarded rules to {discarded_path}")

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


async def _condense_group(structured_llm, directory: str, rules: list) -> tuple[str, list[str], Exception | None]:
    """
    @brief Async helper that prompts the LLM to condense a single directory group of business rules.
    @param structured_llm LLM configured with CondenserOutput structured output.
    @param directory The relative directory name for this group.
    @param rules List of BusinessRule objects to condense.
    @return Tuple of (directory, list of condensed rule strings, error or None).
    """
    try:
        rule_list = "\n".join(f"{i+1}. {r.rule}" for i, r in enumerate(rules))

        system_message = """You are a Senior Software Architect. Your task is to condense a list of business rules by merging rules that are semantically similar or redundant."""

        prompt = f"""Directory: {directory}

Business rules to condense:
{rule_list}

MERGING GUIDELINES:
- Merge rules that express the same constraint or policy in different words.
- Merge rules that are specific instances of a more general pattern. When several rules each describe a similar aspect of the codebase's behaviour but for different cases, combine them into one general rule that captures the shared intent.
- When merging, produce a single clear statement that preserves the meaning of all merged rules. Do not lose important specifics unless they are redundant.
- Do NOT merge rules that govern different aspects of the system, even if they sound superficially similar.
- Do NOT invent new rules that are not supported by the originals.
- Do NOT discard a rule unless it is fully covered by another rule in the list.
- Rules that are already unique and distinct should be kept as-is.

POSITIVE EXAMPLE — rules that SHOULD be merged:
Input:
1. A number can be converted into its written French representation.
2. A number can be converted into its written Arabic representation.
3. A number can be converted into its written Spanish representation.
Output:
1. A number can be converted into written representations in various languages.

NEGATIVE EXAMPLE — rules that should NOT be merged:
Input:
1. Order total must be non-negative.
2. An order must contain at least one item to be processed.
These both relate to order validation, but they enforce different constraints (value range vs. item count). They must remain separate.

Return the condensed list of business rules."""

        messages = [("system", system_message), ("user", prompt)]
        output = await structured_llm.ainvoke(messages)
        return directory, output.condensed_rules, None
    except Exception as e:
        return directory, [], e


async def _validate_single_rule(
    structured_llm,
    rule: CondensedRule,
    code_context: list[str],
    summary_context: list[str],
    is_final_pass: bool,
) -> tuple:
    """
    @brief Async helper that validates a single business rule against retrieved context.
    @param structured_llm LLM configured with ValidatorOutput structured output.
    @param rule The CondensedRule to validate.
    @param code_context List of formatted code context strings for this rule.
    @param summary_context List of formatted summary context strings for this rule.
    @param is_final_pass If True, "need_more_context" is disallowed in the prompt.
    @return Tuple of (rule, ValidatorOutput, error or None).
    """
    try:
        code_text = "\n\n".join(code_context) if code_context else "None"
        summary_text = "\n\n".join(summary_context) if summary_context else "None"

        force_decision_clause = ""
        if is_final_pass:
            force_decision_clause = (
                "\nIMPORTANT: This is the final retrieval pass — maximum context has been gathered. "
                "\"need_more_context\" is NOT available as a decision. You MUST choose either \"valid\" or \"discard\"."
            )

        system_message = (
            "You are a Senior Software Architect acting as a business rule auditor. "
            "Your task is to determine whether a proposed business rule is genuinely supported "
            "by the source code evidence provided. You must be precise and evidence-driven — "
            "never confirm a rule based on assumptions."
        )

        prompt = f"""BUSINESS RULE TO VALIDATE:
Rule ID: {rule.id}
Rule: {rule.rule}
Source directory: {rule.source_directory}
Source files: {", ".join(rule.source_file_paths)}

RETRIEVED CODE CONTEXT:
{code_text}

RETRIEVED FILE SUMMARY CONTEXT:
{summary_text}

WHAT IS A BUSINESS RULE:
A business rule is a constraint, policy, threshold, validation, access control check, or behavioral requirement that governs how the software product behaves for its users or within its problem domain. It is NOT an implementation detail, architectural pattern, or DevOps/infrastructure concern.

TASK:
Determine whether the business rule above is supported by the retrieved code and summary context. Choose exactly one of three outcomes:

1. **valid** — The rule IS supported by concrete evidence in the context. You can point to specific code snippets, method signatures, validation checks, conditional logic, or summary statements that directly enforce or implement the rule.

2. **discard** — The rule is NOT supported, and additional retrieval is unlikely to help. Choose this when:
   - The context covers the relevant area thoroughly but shows no evidence of the rule.
   - The rule contradicts what the code actually does.
   - The rule is too vague or generic to be grounded in any specific code behavior.
   - The rule describes implementation mechanics rather than a business/domain constraint.

3. **need_more_context** — The context is insufficient to make a confident judgement. Choose this ONLY when:
   - The context contains partial hints (e.g., a method call to an unresolved external function) that suggest the rule MIGHT be supported with more code.
   - The source directory or file area hasn't been well covered by retrieval yet.
   - Do NOT choose this as a "safe" fallback. If the context is reasonably thorough and shows no evidence, choose "discard".
{force_decision_clause}

HANDLING BORDERLINE / PARTIAL EVIDENCE:
- If the evidence only partially supports the rule (e.g., the code enforces a narrower version of the stated constraint), choose "valid" but note the narrower scope in your reasoning.
- If the rule is broadly stated but the code only demonstrates one specific case, validate the specific case you can confirm and explain the gap in your reasoning.
- If the code hints at the rule but the logic is ambiguous or incomplete, prefer "need_more_context" over "valid" on the first pass.

RESPONSE INSTRUCTIONS:
- If "valid": populate the `explanation` field with `evidence` (a dict mapping filenames to lists of relevant code snippets that support the rule) and `reasoning` (a clear explanation of how those snippets support the rule).
- If "discard": populate the `discard_reason` field explaining why the rule is not supported.
- If "need_more_context": leave both `explanation` and `discard_reason` as None.

EXAMPLES:

--- Example 1: VALID ---
Rule: "A discount amount must not exceed the order total."
Code context includes:
  [CODE CHUNK]
  File: src/Orders/OrderService.cs
  Container: OrderService
  Name: ApplyDiscount
  Content:
    public void ApplyDiscount(Order order, decimal discount) {{
        if (discount > order.Total)
            throw new ValidationException("Discount exceeds order total");
        order.Discount = discount;
    }}
Expected output:
{{
  "decision": "valid",
  "explanation": {{
    "evidence": {{"OrderService.cs": ["if (discount > order.Total) throw new ValidationException(\\"Discount exceeds order total\\");"]}},
    "reasoning": "The ApplyDiscount method explicitly checks that the discount does not exceed the order total and throws a ValidationException if it does, directly enforcing this business rule."
  }},
  "discard_reason": null
}}

--- Example 2: DISCARD ---
Rule: "Users must verify their email before placing an order."
Code context includes:
  [CODE CHUNK]
  File: src/Orders/OrderService.cs
  Container: OrderService
  Name: PlaceOrder
  Content:
    public Order PlaceOrder(User user, Cart cart) {{
        ValidateCart(cart);
        var order = new Order(user.Id, cart.Items, cart.Total);
        _orderRepository.Save(order);
        return order;
    }}
  [SUMMARY NODE]
  Path: src/Orders/OrderService.cs
  Content: "Handles order creation, cart validation, and persistence. No authentication or email verification logic present."
Expected output:
{{
  "decision": "discard",
  "explanation": null,
  "discard_reason": "The PlaceOrder method validates the cart and creates the order without any email verification check. The file summary explicitly states no email verification logic is present. The rule is not supported."
}}

--- Example 3: NEED MORE CONTEXT ---
Rule: "Tax is calculated based on the shipping destination's tax rate."
Code context includes:
  [CODE CHUNK]
  File: src/Orders/OrderService.cs
  Container: OrderService
  Name: CalculateTotal
  Content:
    public decimal CalculateTotal(Cart cart, Address shippingAddress) {{
        var subtotal = cart.Items.Sum(i => i.Price);
        var tax = _taxService.ComputeTax(subtotal, shippingAddress);
        return subtotal + tax;
    }}
Expected output:
{{
  "decision": "need_more_context",
  "explanation": null,
  "discard_reason": null
}}
(The method delegates tax computation to _taxService.ComputeTax, which is not in the retrieved context. More code from the TaxService class could confirm whether tax is indeed based on the shipping address's rate.)"""

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
