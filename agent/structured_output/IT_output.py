"""
@file IT_output.py
@brief Defines structured output models for the Integration Test generation agent (G3).
@details Includes models for condensed validated rules with evidence and unit tests.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from agent.UT_agent import ValidatedRule

class Explanation(BaseModel):
    """
    @brief Contains evidence and reasoning that support a validated integration test
    """
    model_config = ConfigDict(extra="forbid")
    evidence: dict[str, list[str]] = Field(..., description="Dictionary mapping filenames to lists of code snippets that support the tests.")
    reasoning: str = Field(..., description="Explanation of how the retrieved code snippets imply or support the tests.")

class WorkflowGroupOutput(BaseModel):
    workflow_name: str = Field(...,description="Name of the workflow to be tested")
    workflow_description: str = Field(...,description="description of the workflow to be tested")
    rule_ids: list[int] = Field(..., description="List of rules ids pertinent to the workflow")
class WorkflowGroup(BaseModel):
    """
    @brief Represents a single workflow's group of related business rules.
    """
    workflow_name: str = Field(...,description="Name of the workflow to be tested")
    workflow_description: str = Field(...,description="description of the workflow to be tested")
    rules: list[ValidatedRule] = Field(..., description="List of rules pertinent to the workflow")

class WorkflowGroups(BaseModel):
    """
    @brief Represents multiple workflow groups.
    """
    workflows: list[WorkflowGroupOutput]

class IntegrationTest(BaseModel):
    """
    @brief Represents a generated integration test for a complete business workflow.
    """
    model_config = ConfigDict(extra="forbid")
    workflow_name: str = Field(...,description="Name of the workflow this integration test validates.")
    workflow_description: str = Field(...,description="Description of the workflow being tested.")
    rule_ids: list[int] = Field(default_factory=list,description="Business rule IDs covered by this workflow test.")
    imports: list[str] = Field(default_factory=list)

    @field_validator("imports")
    @classmethod
    def clean_imports(cls, imports):
        cleaned = []

        for imp in imports:
            imp = imp.strip()

            if imp.startswith("using "):
                imp = imp[6:]

            imp = imp.rstrip(";")

            if "/" in imp or "\\" in imp:
                continue

            cleaned.append(imp)

        return cleaned
    integration_test: str = Field(...,description="Executable integration test method for the workflow.")