"""
@file UTV_output.py
@brief Defines structured output models for the Unit Test generation agent (G3).
@details Includes models for condensed validated rules with evidence and unit tests.
"""

from pydantic import BaseModel, Field, ConfigDict

class Explanation(BaseModel):
    """
    @brief Contains evidence and reasoning that support a validated business rule.
    """
    model_config = ConfigDict(extra="forbid")
    evidence: dict[str, list[str]] = Field(..., description="Dictionary mapping filenames to lists of code snippets that support the rule.")
    reasoning: str = Field(..., description="Explanation of how the retrieved code snippets imply or support the validated rule.")

class UnitTest(BaseModel):
    """
    @brief Represents unit tests generated that correspond to a validated business rule
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Stable unique identifier matching the ValidatedRule ID.")
    rule: str = Field(..., description="The business rule statement that this unit test corresponds to.")
    imports: list[str] = Field(default_factory=list, description="List of import statements required for the unit test (one per list item), in the correct syntax for the target language.")
    source_directory: str = Field(..., description="The directory this test pertains to.")
    source_file_paths: list[str] = Field(default_factory=list, description="File paths from which this test was originally derived.")
    unit_test: str = Field(..., description = "Corresponding Unit Test generated for a validated business rule")

class ValidatedTest(BaseModel):
    """
    @brief Represents unit tests that have been validated to be true 
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description = "Stable unique identifier matching the ValidatedRule ID.")
    rule: str = Field(..., description = "The validated rule statement that the unit test corresponds to.")
    imports: list[str] = Field(..., description = "List of import statements that are required for the unit test code to run.")
    unit_test: str = Field(..., description = "Corresponding unit test code that has been validated.")
    explanation: Explanation = Field(..., description = "Evidence and reasoning supporting the rule's validity")

class DiscardedTest(BaseModel):
    """
    @brief Represents unit tests that have been discarded to be true 
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description = "Stable unique identifier matching the ValidatedRule ID.")
    rule: str = Field(..., description = "The validated rule statement that the unit test corresponds to.")
    imports: list[str] = Field(..., description = "List of import statements that are required for the unit test code to run.")
    unit_test: str = Field(..., description = "Corresponding unit test code that has been validated.")
    reason: str = Field(..., description = "Reason as to why the unit test was discarded")
