"""
@file backend/lsp/language.py
@brief Selects the right server for the codebase depending on the detected language.
@details This module provides a function to detect the programming language of a file based on its extension
"""

from pathlib import Path
from lsp_client import PyrightClient, GoplsClient, RustAnalyzerClient, TypescriptClient, DenoClient
from lsp.language import detect_language
from lsp.base_client import LSPClient

class LSPManager:
    """
    Manages the Language Server Protocol (LSP) client based on the detected programming language of a file.
    """

    CLIENTS = {
        "python": PyrightClient,
        "go": GoplsClient,
        "rust": RustAnalyzerClient,
        "typescript": TypescriptClient,
        "deno": DenoClient,
    }

    def __init__(self, codebase_path: str | Path):
        self.codebase_path = Path(codebase_path).resolve()
        self.languages = self._detect_languages()
        

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
    

    def _detect_languages(self):
        """
        Detects the programming languages present in the codebase.

        Returns:
            A set of detected programming languages.
        """
        languages = set()
       
        for file_path in self.codebase_path.rglob("*"):
        
            if file_path.is_file():
                language = detect_language(file_path)
                if language:
                    languages.add(language)
        return languages
    
    def get_client_class(self, file_path: str | Path):
        """
        Returns the LSP client class for the given programming language.

        Args:
            file_path (str | Path): The path to the file for which to get the LSP client class.

        Returns:
            The corresponding LSP client class.
        """
        language = detect_language(file_path)

        if language not in self.CLIENTS:
            raise ValueError(f"No LSP client available for language: {language}")

        return self.CLIENTS.get(language)

    def create_client(self, file_path: str | Path):
        """
        Creates an instance of the selected LSP client for the given file.

        Args:
            file_path (str | Path): The path to the file for which to create the LSP client."
        """
        client_class = self.get_client_class(file_path)
        return LSPClient(self.codebase_path, client_class=client_class)