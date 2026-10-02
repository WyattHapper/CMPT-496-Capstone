from dataclasses import dataclass, field
from pathlib import Path

from lsp.models import DocumentSymbol, Definition, Reference

@dataclass
class FileContext:
    """
    Represents the context of a file in the workspace.

    Attributes:
        file_path (Path): The path to the file.
        document_symbols (list[DocumentSymbol]): A list of document symbols in the file.
        definitions (list[Definition]): A list of definitions in the file.
        references (list[Reference]): A list of references in the file.
    """
    file_path: Path
    language: str

    symbols: list[DocumentSymbol] = field(default_factory=list)
    definitions: list[Definition] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)

