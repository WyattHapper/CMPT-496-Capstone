"""
@file client.py
@brief Wrapper around the LSP client dependency.
"""
from contextlib import AsyncExitStack
from pathlib import Path
from lsp_client import PyrightClient, Position
from lsp.models import (
    Position as ModelPosition,
    Range,
    Location,
    Definition,
    Reference,
)


class LSPClient:
    """
    Provides a simple interface for communicating with an LSP server.

    This class should not contain language-specific logic.
    """

    def __init__(
        self,
        workspace_path: str | Path,
        client_class=PyrightClient
    ):
       
        self.workspace_path = Path(workspace_path).resolve()
        self._client = client_class(self.workspace_path)

        self._exit_stack = AsyncExitStack()

    async def __aenter__(self):
        """
        Start the LSP client and enter the async context.

        Returns:
            LSPClient: The instance of the LSPClient.
        """
        self._client = await self._exit_stack.enter_async_context(self._client)

        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        """
        Exit the async context and clean up resources.
        
        Returns:
            None
        """
        
        return await self._exit_stack.__aexit__(exc_type, exc_value, traceback)

    
    async def open_file(self, file_path: str | Path, file_content: str):
        """
        Notify the server that a file has been opened.
        Args:
            file_path: The path to the file being opened.
            file_content: The content of the file being opened.

        """
        file_path = Path(file_path).resolve()

        await self._client.notify_text_document_opened(file_path, file_content)


    async def get_definitions(self, file_path, line: int, character: int):
        """
        Get definitions at a particular position.
        Args:
            file_path: The path to the file.
            line: The line number (0-based).
            character: The character offset on the line (0-based).
        Returns:
            A list of Definition objects representing the definitions found at the specified position.

        """

        file_path = Path(file_path).resolve()
        position = Position(line=line, character=character)

        results = await self._client.request_definition(file_path, position)
        
        if results is None:
            return []  
        
        return [Definition(location=self._convert_location(location)) for location in results]
    


    async def get_references(self, file_path, line: int, character: int, include_declaration: bool = True):
        """
        Get references at a particular position.
        Args:
            file_path: The path to the file.
            line: The line number (0-based).
            character: The character offset on the line (0-based).
            include_declaration: Whether to include the declaration in the results.

        Returns:
            A list of Reference objects representing the references found at the specified position.
        """

        file_path = Path(file_path).resolve()

        position = Position(line=line, character=character)

        results =  await self._client.request_references(
                    file_path,
                    position,
        )

        if results is None:
            return []
        
        return [Reference(location=self._convert_location(location)) for location in results]

    def _convert_location(self, location: Location) -> Location:
            """
            Convert a location from the LSP client to the internal Location model.
            Args:
                location: The location object from the LSP client.
            Returns:
                Location: The converted Location object.
            """
            return Location(
                file_path=location.uri,
                range=Range(
                    start=ModelPosition(line=location.range.start.line, character=location.range.start.character),
                    end=ModelPosition(line=location.range.end.line, character=location.range.end.character)
                )
            )