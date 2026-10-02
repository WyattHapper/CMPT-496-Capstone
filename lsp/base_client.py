"""
@file base_client.py
@brief Wrapper around the LSP client dependency.
"""
from contextlib import AsyncExitStack
from pathlib import Path
from lsp_client import Position
from lsp.models import (
    Position as ModelPosition,
    Range,
    Location,
    Definition,
    Reference,
    DocumentSymbol,
)


class LSPClient:
    """
    Provides a simple interface for communicating with an LSP server.

    This class should not contain language-specific logic.
    """

    def __init__(
        self,
        workspace_path: str | Path,
        client_class
    ):
       
        self.workspace_path = Path(workspace_path).resolve()
        self._client = client_class(workspace=self.workspace_path)

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

        relative_path = file_path.relative_to(self.workspace_path)

        await self._client.notify_text_document_opened(relative_path, file_content)


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
        relative_path = file_path.relative_to(self.workspace_path)
        position = Position(line=line, character=character)

        results = await self._client.request_definition(relative_path, position)
        
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
        relative_path = file_path.relative_to(self.workspace_path)

        position = Position(line=line, character=character)

        results =  await self._client.request_references(
                    relative_path,
                    position,
        )

        if results is None:
            return []
        
        return [Reference(location=self._convert_location(location)) for location in results]
    

    async def get_document_symbols(self, file_path):
        """
        Get document symbols for a particular file.
        Args:
            file_path: The path to the file.
        Returns:
            A list of DocumentSymbol objects representing the symbols found in the specified file.
        """
        file_path = Path(file_path).resolve()
        relative_path = file_path.relative_to(self.workspace_path)

        results = await self._client.request_document_symbol(relative_path)

        if results is None:
            return []
        
        return [self._convert_document_symbol(symbol) for symbol in results]

    
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
    
    def _convert_document_symbol(self, symbol) -> DocumentSymbol:
        """
        Convert a document symbol from the LSP client to the internal DocumentSymbol model.
        Args:
            symbol: The document symbol object from the LSP client.
        Returns:
            DocumentSymbol: The converted DocumentSymbol object.
        """

        converted_children = []

        if symbol.children:
            for child in symbol.children:
                converted_children.append(self._convert_document_symbol(child))
            
        return DocumentSymbol(
            name=symbol.name,
            kind=symbol.kind.value,
            range=self._convert_range(symbol.range),
            selection_range=self._convert_range(symbol.selection_range),
            detail=symbol.detail,
            children=converted_children
        )
    
    def _convert_range(self, range) -> Range:
        """
        Convert a range from the LSP client to the internal Range model.
        Args:
            range: The range object from the LSP client.
        Returns:
            Range: The converted Range object.
        """
        return Range(
            start=ModelPosition(line=range.start.line, character=range.start.character),
            end=ModelPosition(line=range.end.line, character=range.end.character)
        )