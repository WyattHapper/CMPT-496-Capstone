"""
@file IT_output.py
@brief Defines structured output models for the Integration Test generation agent (G3).
@details Includes models for condensed validated rules with evidence and unit tests.
"""

from pydantic import BaseModel, Field, ConfigDict

class Explanation(BaseModel):
    """
    @brief Contains evidence and reasoning that support a validated integration test
    """
    model_config = ConfigDict(extra="forbid")
    evidence: dict[str, list[str]] = Field(..., description="Dictionary mapping filenames to lists of code snippets that support the tests.")
    reasoning: str = Field(..., description="Explanation of how the retrieved code snippets imply or support the tests.")


class ValidatedRule(BaseModel):
    """
    @brief Represents a business rule that has been validated with supporting evidence.
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Stable unique identifier matching the validated ID.")
    rule: str = Field(..., description="The business rule statement.")
    source_directory: str = Field(..., description="The directory this rule pertains to.")
    source_file_paths: list[str] = Field(default_factory=list, description="File paths that were retrieved as evidence for this rule.")
    explanation: Explanation = Field(..., description="Evidence and reasoning supporting the rule's validity.")

class IntegrationTest(BaseModel):
    """
    @brief Represents integration tests generated that correspond to a validated business rule
    """
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Stable unique identifier matching the ValidatedRule ID.")
    rule: str = Field(..., description="The business rule statement that this integration test corresponds to.")
    imports: list[str] = Field(default_factory=list, description="List of import statements required for the integration test (one per list item), in the correct syntax for the target language.")
    source_directory: str = Field(..., description="The directory this test pertains to.")
    source_file_paths: list[str] = Field(default_factory=list, description="File paths from which this test was originally derived.")
    integration_test: str = Field(..., description = "Corresponding Integration Test generated for a validated business rule")