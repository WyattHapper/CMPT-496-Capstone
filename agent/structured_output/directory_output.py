"""
@file directory_output.py
@brief This file defines the DirectoryOutput class, which is used to represent the structured output of a summary of a directory's contents and purpose.
@details Includes a nested class for a directory's contents (files and subdirectories) as well as fields for the directory's purpose, responsibilities, and unresolved questions.
"""

from typing import Optional
from pydantic import BaseModel, Field

class DirectoryContents(BaseModel):
    """
    @brief A pydantic BaseModel representing the contents of a directory, including lists of files and subdirectories.
    """
    files: Optional[list[str]] = Field(default_factory=list, description="A list of files contained in the directory. These should be listed as only filenames, not including paths. Leave as an empty list if there are no files or if they cannot be determined.")
    subdirectories: Optional[list[str]] = Field(default_factory=list, description="A list of subdirectories contained in the directory. Leave as an empty list if there are no subdirectories or if they cannot be determined.")

class DirectoryOutput(BaseModel):
    """
    @brief A pydantic BaseModel representing the structured output of a summary of a directory.
    """
    directory_name: str = Field(..., description="The name of the directory being summarized.")
    directory_path: str = Field(..., description="The full relative path of the directory being summarized, from the root of the codebase.")
    contents: DirectoryContents = Field(..., description="The contents of the directory, including lists of files and subdirectories. This field is required, but the lists within it may be empty if there are no files or subdirectories or if they cannot be determined.")
    purpose: str = Field(..., description="A concise summary of the purpose of the directory and its contents. This should be a high-level overview of what the directory is for and how it fits into the overall codebase, rather than a detailed description of specific files or subdirectories contained within it.")
    responsibilities: Optional[list[str]] = Field(default_factory=list, description="A list of specific tasks or domains this directory handles (e.g., 'User Authentication', 'Database Migrations'). Leave as an empty list if there are no specific responsibilities that can be identified or if they cannot be determined.")
    unresolved_questions: Optional[list[str]] = Field(default_factory=list, description="A list of questions that remain unanswered about the directory and its contents, which may require additional context to properly answer. Leave as an empty list if there are no such questions.")