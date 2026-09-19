"""
@file client.py
@brief Wrapper around the LSP client dependency.
"""
from contextlib import AsyncExitStack
from pathlib import Path
from lsp_client import PyrightClient, Position


class LSPClient:
    """
    Provides a simple interface for communicating with an LSP server.

    This class should not contain language-specific logic.
    """

    def __init__(
        self,
        workspace_path: str | Path,
    ):
       
        self.workspace_path = Path(workspace_path).resolve()
        self._client = PyrightClient(workspace=self.workspace_path)

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

        return await self._client.request_definition(file_path, position)
    


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

        return await self._client.request_references(
                    file_path,
                    position,
                    include_declaration=include_declaration
        )

   