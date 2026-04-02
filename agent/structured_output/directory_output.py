"""
@file directory_output.py
@brief This file defines the DirectoryOutput class, which is used to represent the structured output of a summary of a directory's contents and purpose.
@details Includes a nested class for a directory's contents (files and subdirectories) as well as fields for the directory's purpose, responsibilities, and unresolved questions.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

"""
class DirectoryContents(BaseModel):
    
    @brief A pydantic BaseModel representing the contents of a directory, including lists of files and subdirectories.
    
    files: Optional[list[str]] = Field(default_factory=list, description="A list of files contained in the directory. These should be listed as only filenames, not including paths. Leave as an empty list if there are no files or if they cannot be determined.")
    subdirectories: Optional[list[str]] = Field(default_factory=list, description="A list of subdirectories contained in the directory. Leave as an empty list if there are no subdirectories or if they cannot be determined.")
"""

class DirectoryOutput(BaseModel):
    """
    @brief A pydantic BaseModel representing the structured output of a summary of a directory.
    """
    model_config = ConfigDict(extra="forbid")
    directory_name: str = Field(..., description="The name of the directory being summarized.")
    directory_path: str = Field(..., description="The full relative path of the directory being summarized, from the root of the codebase.")
    # contents: DirectoryContents = Field(..., description="The contents of the directory, including lists of files and subdirectories. This field is required, but the lists within it may be empty if there are no files or subdirectories or if they cannot be determined.")
    purpose: str = Field(..., description="A summary of the purpose of the directory and its contents. This should be a high-level overview of what the directory is for and how it fits into the overall codebase, rather than a detailed description of specific files or subdirectories contained within it.")
    responsibilities: Optional[list[str]] = Field(default_factory=list, description="A list of specific tasks or domains this directory handles (e.g., 'User Authentication', 'Database Migrations'). Leave as an empty list if there are no specific responsibilities that can be identified or if they cannot be determined.")
    # unresolved_questions: Optional[list[str]] = Field(default_factory=list, description="A list of questions that remain unanswered about the directory and its contents, which may require additional context to properly answer. Leave as an empty list if there are no such questions.")

class ContextAnalysisOutput(BaseModel):
    """
    @brief A pydantic BaseModel representing the output of the context analysis node.
    """
    model_config = ConfigDict(extra="forbid")
    sufficient_code_context: bool = Field(description="Whether the retrieved code context is sufficient to summarize the current directory.")
    sufficient_summary_context: bool = Field(description="Whether the retrieved summary context is sufficient to summarize the current directory.")
    recommended_codebase_k_increase: int = Field(default=0,description="How many more code snippets to retrieve.")
    recommended_file_summary_k_increase: int = Field(default=0,description="How many more file summaries to retrieve.")

class JudgementOutput(BaseModel):
    """
    @brief A pydantic Basemodel representing the output of the judgement node.
    """
    model_config = ConfigDict(extra="forbid")
    summary_acceptable: bool = Field(..., description="Whether the generated directory summary is satisfactory and meets the required standards.")
    feedback: Optional[str] = Field(default=None, description="Detailed information regarding the evaluation of the generated directory summary, including any identified strengths, weaknesses, or areas for improvement. This field may be left empty if the summary is deemed satisfactory or if specific feedback cannot be provided.")

class BusinessRulesOutput(BaseModel):
    """
    @brief A pydantic BaseModel representing the business rules extracted from a directory.
    """
    model_config = ConfigDict(extra="forbid")
    directory_name: str = Field(None, description="The name of the directory for which business rules were extracted. Filled in by code post LLM call")
    directory_path: str = Field(None, description="The full relative path of the directory, from the root of the codebase. Filled in by code post LLM call")
    observed_rules: list[str] = Field(default_factory=list, description="Business rules or domain policies that the system clearly enforces. Each rule should be a plain-language statement of what the system requires, allows, or prevents — without referencing implementation details like method signatures or design patterns. Do not provide evidence or reasoning, just list the buisness rule (when applicable)")
    inferred_rules: list[str] = Field(default_factory=list, description="Business rules or domain policies that are implied by the system's behavior but not explicitly named. Each entry must begin with 'Inference:' and describe the implied rule in plain, non-technical language. Do not provide evidence or reasoning, just list the buisness rule (when applicable).")