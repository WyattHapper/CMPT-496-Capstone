"""
@file backend/lsp/language.py
@brief Selects the right server for the codebase depending on the detected language.
@details This module provides a function to detect the programming language of a file based on its extension
"""

from pathlib import Path
from lsp_client import PyrightClient, GoplsClient, RustAnalyzerClient, TypescriptClient, DenoClient
from lsp.language import detect_language
from lsp.client import LSPClient

class LSPManager:
    """
    Manages the Language Server Protocol (LSP) client based on the detected programming language of a file.
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path).resolve()
        self.language = detect_language(self.file_path)
        self.client_class = self._select_client()

    def _select_client(self):
        """
        Selects the appropriate LSP client based on the detected programming language.

        Returns:
            An instance of the appropriate LSP client.
        """
        if self.language == "python":
            return PyrightClient
        elif self.language == "typescript":
            return TypescriptClient
        elif self.language == "rust":
            return RustAnalyzerClient
        else:
            raise ValueError(f"No LSP client available for language: {self.language}")
        
    def create_client(self, workspace_path: str | Path):
        """
        Creates an instance of the selected LSP client.

        Returns:
            An instance of the selected LSP client.
        """
        return LSPClient(workspace_path, client_class=self.client_class)