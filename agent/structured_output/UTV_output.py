"""
@file UT_output.py
@brief Defines structured output models for the Unit Test generation agent (G3).
@details Includes models for condensed validated rules with evidence and unit tests.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

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
    source_file_paths: list[str] = Field(default_factory=list, description="File paths that were retrieved as evidence for this rule.")
    explanation: Explanation = Field(..., description="Evidence and reasoning supporting the rule's validity.")

class UnitTest(BaseModel):
    """
    @brief Represents unit tests generated that correspond to a validated business rule
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Stable unique identifier matching the ValidatedRule ID.")
    rule: str = Field(..., description="The business rule statement that this unit test corresponds to.")
    unit_test: str = Field(..., description = "Corresponding Unit Test generated for a validated business rule")