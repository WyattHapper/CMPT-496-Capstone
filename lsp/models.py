"""
@file backend/lsp/models.py
@brief Data models for LSP interactions.
@details This module defines data models used for interactions with Language Server Protocol (LSP) servers.
"""

from pydantic import BaseModel, Field

class position(BaseModel):
    """
    Represents a position in a text document.

    Attributes:
        line (int): The line number (0-based).
        character (int): The character offset on the line (0-based).
    """
    line: int = Field(..., ge=0, description="The line number (0-based).")
    character: int = Field(..., ge=0, description="The character offset on the line (0-based).")

class range(BaseModel):
    """
    Represents a range in a text document.

    Attributes:
        start (position): The start position of the range.
        end (position): The end position of the range.
    """
    start: position
    end: position

class location(BaseModel):
    """
    Represents a location in a text document.

    Attributes:
        file_path (str): The path to the file.
        range (range): The range within the file.
    """
    file_path: str
    range: range

class Symbol(BaseModel):
    """
    Represents a symbol in a text document.

    Attributes:
        name (str): The name of the symbol.
        kind (int): The kind of the symbol (e.g., function, variable).
        location (location): The location of the symbol in the document.
    """
    name: str
    kind: str
    location: location



class Definition(BaseModel):
    """
    Represents a definition in a text document.

    Attributes:
        location (location): The location of the definition in the document.
    """
    symbol_name: str
    location: location


class reference(BaseModel):
    """
    Represents a reference to a symbol in a text document.

    Attributes:
        location (location): The location of the reference in the document.
    """
    symbol_name: str
    location: location