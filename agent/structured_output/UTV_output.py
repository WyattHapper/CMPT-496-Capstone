"""
@file UTV_output.py
@brief Defines structured output models for the Unit Test Validation agent (G3).
@details Includes models for unit test candidates, execution reports, and validator decisions.
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

class Report(BaseModel):
    """
    @brief Represents the unit test reports that are executed
    """
    model_config = ConfigDict(extra="forbid")
    return_code: int = Field(..., description="Return code for the report. 0 if all pass. 1 if at least one failure")
    output: str = Field(..., description="Output from the results of the executed tests")
    errors: str = Field(..., description="Errors from the results of the executed tests")

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

class ValidatorOutput(BaseModel):
    """
    @brief class that represents the ouptut given from the validator node
    @details The LLM assesses the tests validity based on code context and determines if the test is valid, discarded or needs more context
    """
    model_config = ConfigDict(extra="forbid")
    decision: Literal["failure", "success"] = Field(None, description = "The validator's decision: 'failure' if the unit test function failed when executed. 'success' if the unit test function succeeded.")
    unit_test: Optional[str] = Field(
        None,
        description="Updated unit test after the LLM fixes it. Populate only when decision is 'failure'."
    )
    imports: Optional[list[str]] = Field(
        None,
        description="Updated imports after the LLM fixes it. Populate only when decision is 'failure'."
    )

