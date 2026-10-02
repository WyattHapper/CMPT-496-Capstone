from pathlib import Path

from lsp.language import detect_language
from lsp.base_client import LSPClient
from lsp.context import FileContext
from contextlib import AsyncExitStack

#language-specific client imports go here
import lsp.clients.csharp as csharp_client



class LSPManager:
    """
    Manages language-specific LSP clients for a given codebase.

    This class is responsible for detecting the programming languages
    used in the codebase and providing access to the appropriate
    language-specific LSP clients.
    """

    CLIENTS = {
        "csharp": csharp_client.CSharpClient,
    }

    def __init__(self, codebase_path: str | Path):
        self.codebase_path = Path(codebase_path)
        self.languages = self.detect_languages()

        self._stack = AsyncExitStack()
        self.clients = {}
        
    async def __aenter__ (self):

        for language in self.languages:
            
            client_class = self.get_client_class(language)

            if client_class is None:
                print(f"No LSP client registered for {language}, skipping.")
                continue

            client = client_class(self.codebase_path)
            client = await self._stack.enter_async_context(client)

            self.clients[language] = client
        
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):

        await self._stack.aclose()

        

    def detect_languages(self) -> set[str]:
        """
        Detects the programming languages used in the codebase.

        Returns:
            set[str]: A set of detected programming languages.
        """
        detected_languages = set()
        for file_path in self.codebase_path.rglob("*"):
            if file_path.is_file():
                language = detect_language(file_path)
                if language:
                    detected_languages.add(language)
        return detected_languages

    
    def get_language(self, file_path: str | Path) -> str | None:
        """
        Detects the programming language of a specific file.

        Args:
            file_path: Path to the source file.

        Returns:
            The detected programming language, or None if it cannot be detected.
        """
        return detect_language(file_path)
    
    def get_client(self, file_path: str | Path):
        language = self.get_language(file_path)

    
        if language is None:
            return None
        
        return self.clients.get(language)

    def get_client_class(self, language: str):
        """
        Returns the appropriate LSP client class for a given programming language.

        Args:
            language (str): The programming language.
        """

       
        if language is None:
            raise ValueError("Language cannot be None")
        
        client_class = self.CLIENTS.get(language)

        # if client_class is None:
        #     raise ValueError(
        #         f"No LSP client class found for language: {language}"
        #     )

       
        
        # Add more language-specific client classes here as needed
        return client_class
    
    def create_client(self, language: str) -> LSPClient | None:
        """
        Creates a language-specific LSP client for the given programming language.

        Args:
            language (str): The programming language.
        """
        client_class = self.get_client_class(language)

        if client_class is None:
            return None
       
        return client_class(self.codebase_path)
    

    async def get_file_context(self, file_path: str | Path):

        file_path = Path(file_path)

        language = self.get_language(file_path)

        if language is None:
            return None
        
        client = self.get_client(file_path)

        if client is None:
            return None
        
        symbols = await client.get_document_symbols(file_path)

        return FileContext(file_path = file_path, language = language, symbols = symbols)
      