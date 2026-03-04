"""
@file file_summary_output.py
@brief This file defines the FileSummaryOutput class, which is used to represent the structured output of a summary of a file's contents.
@details This file defines a nested structured output format for LLM summarization of a code file's contents, including separate classes for
function and class summaries
"""

from typing import Optional
from pydantic import BaseModel, Field

class FunctionSummary(BaseModel):
    """
    @brief A pydantic BaseModel representing a summary of a function defined in a code file.
    """
    # Required fields
    name: str = Field(..., description="The name of the function.")
    description: str = Field(..., description="A concise description of what the function does.")

    # Optional fields
    parameters: Optional[list[str]] = Field(default_factory=list, description="A list of parameters that the function takes, if applicable. Leave as an empty list if there are no parameters")
    return_type: Optional[str] = Field(None, description="The return type of the function, if applicable. Leave as null if there is no return type or if it cannot be determined.")
    calls: Optional[list[str]] = Field(None, description="A list of other functions that this function calls, if applicable. Leave as an empty list if there are no calls or if they cannot be determined.")

class ClassSummary(BaseModel):
    """
    @brief A pydantic BaseModel representing a summary of a class defined in a code file.
    """
    # Required fields
    name: str = Field(..., description="The name of the class.")
    description: str = Field(..., description="A concise description of what the class does.")

    # Optional fields
    methods: Optional[list[FunctionSummary]] = Field(default_factory=list, description="A list of methods defined in this class, if applicable. Leave as an empty list if there are no methods or if they cannot be determined.")

class FileSummaryOutput(BaseModel):
    """
    @brief A pydantic BaseModel representing a summary of a file's contents.
    """
    # Required fields
    path: str = Field(..., description="The path of the file being summarized.")
    summary: str = Field(..., description="A concise summary of the file contents.")

    # Optional fields
    dependencies: Optional[list[str]] = Field(default_factory=list, description="A list of external libraries and imports used in this file, if applicable. Leave as an empty list if there are no dependencies or if they cannot be determined.")
    calls: Optional[list[str]] = Field(default_factory=list, description="A list of function calls made in this file, but not within a function body, if applicable. Leave as an empty list if there are no such function calls or if they cannot be determined.")
    functions: Optional[list[FunctionSummary]] = Field(default_factory=list, description="A list of functions defined in this file, but not within a class, if applicable. Leave as an empty list if there are no such functions or if they cannot be determined.")
    classes: Optional[list[ClassSummary]] = Field(default_factory=list, description="A list of classes defined in this file, if applicable. Leave as an empty list if there are no classes or if they cannot be determined.")