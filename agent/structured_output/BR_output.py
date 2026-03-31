"""
@file BR_output.py
@brief Defines structured output models for the Business Rule validation agent (G3).
@details Includes models for condensed rules, validated rules with evidence,
discarded rules with reasons, and structured LLM outputs for the condenser
and validator nodes.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class CondensedRule(BaseModel):
    """
    @brief Represents a business rule after the condensation step.
    @details Carries the deduplicated rule text along with provenance metadata
    (source directory and file paths) needed by the retriever and validator.
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Stable unique identifier for the rule, assigned sequentially by the condenser node.")
    rule: str = Field(..., description="The condensed business rule statement.")
    source_directory: str = Field(..., description="The directory this rule pertains to.")
    source_file_paths: list[str] = Field(default_factory=list, description="File paths from which this rule was originally derived. May span multiple files if the condenser merged related rules.")


class Explanation(BaseModel):
    """
    @brief Contains evidence and reasoning that support a validated business rule.
    """
    model_config = ConfigDict(extra="forbid")
    evidence: dict[str, list[str]] = Field(..., description="Dictionary mapping filenames to lists of code snippets that support the rule.")
    reasoning: str = Field(..., description="Explanation of how the retrieved code snippets imply or support the business rule.")


class ValidatedRule(BaseModel):
    """
    @brief Represents a business rule that has been validated with supporting evidence.
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Stable unique identifier matching the CondensedRule ID.")
    rule: str = Field(..., description="The business rule statement.")
    source_directory: str = Field(..., description="The directory this rule pertains to.")
    explanation: Explanation = Field(..., description="Evidence and reasoning supporting the rule's validity.")


class DiscardedRule(BaseModel):
    """
    @brief Represents a business rule that was rejected during validation.
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Stable unique identifier matching the CondensedRule ID.")
    rule: str = Field(..., description="The business rule statement.")
    source_directory: str = Field(..., description="The directory this rule pertains to.")
    reason: str = Field(..., description="Explanation of why the rule was discarded.")


class CondenserOutput(BaseModel):
    """
    @brief Structured LLM output from the condenser node.
    @details Returns condensed rule strings for a single directory group.
    The condenser node is responsible for wrapping these in CondensedRule
    objects with IDs and provenance metadata.
    """
    model_config = ConfigDict(extra="forbid")
    condensed_rules: list[str] = Field(..., description="List of condensed/deduplicated business rule statements for a single directory group.")


class ValidatorOutput(BaseModel):
    """
    @brief Structured LLM output from the combined validator node.
    @details The validator assesses context sufficiency and rule validity in a
    single LLM call. The decision field forces the model to choose one of three
    outcomes, and the conditional fields are populated accordingly.
    """
    model_config = ConfigDict(extra="forbid")
    decision: Literal["need_more_context", "valid", "discard"] = Field(
        ...,
        description="The validator's decision: 'need_more_context' if retrieval should be retried with increased depth, 'valid' if the rule is supported by evidence, 'discard' if the rule cannot be substantiated.")
    explanation: Optional[Explanation] = Field(
        None,
        description="Evidence and reasoning supporting the rule. Populated when decision is 'valid', otherwise None.")
    discard_reason: Optional[str] = Field(
        None,
        description="Explanation of why the rule was discarded. Populated when decision is 'discard', otherwise None.")
