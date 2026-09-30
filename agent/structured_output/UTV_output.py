"""
@file UTV_output.py
@brief Defines structured output models for the Unit Test Validation agent (G3).
@details Includes the unit test candidate model and the AI's answer when it repairs a test
that does not compile (shared with the integration test agent via agent/test_harness.py).
"""
from pydantic import BaseModel, Field, ConfigDict

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

class TestRepair(BaseModel):
    """
    @brief The AI's corrected version of a generated test that failed to compile.
    @details An empty test_method means the AI could not fix it, and the test is dropped.
    """
    __test__ = False  # not a pytest test class
    model_config = ConfigDict(extra="forbid")
    imports: list[str] = Field(default_factory=list, description="Every using directive the test needs, one per entry, e.g. 'using Xunit;'.")
    test_method: str = Field("", description="The corrected test method(s) with their [Fact] or [Theory] attribute, and nothing else. Empty if the test cannot be fixed.")
