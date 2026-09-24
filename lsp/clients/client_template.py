from lsp.base_client import LSPClient
from pathlib import Path

class ClientTemplateName(LSPClient):
    """
    A template for creating a new LSP client.

    This class should be customized for a specific programming language.
    """

    LANGUAGE = "template_language"  # Replace with the actual language name
    FILE_EXTENSIONS = [".template"]  # Replace with the actual file extensions
    PROJECT_FILE_EXTENSIONS = [".templateproj"]  # Replace with the actual project file extensions
    SERVER_COMMAND = ""  # Replace with the actual server command



    def __init__(self, workspace_path: str | Path):
        super().__init__(workspace_path)

    def start(self):
        """
        Start the LSP server.

        This method should be implemented to start the LSP server for the specific language.
        """
        raise NotImplementedError("The start method must be implemented in the subclass.")
    
    def stop(self):
        """
        Stop the LSP server.

        This method should be implemented to stop the LSP server for the specific language.
        """
        raise NotImplementedError("The stop method must be implemented in the subclass.")
    
    def open_file(self, file_path: str | Path, file_content: str):
        """
        Notify the server that a file has been opened.

        This method should be implemented to handle the opening of files for the specific language.
        """
        raise NotImplementedError("The open_file method must be implemented in the subclass.")
    
    def get_symbols(self, file_path: str | Path):
        """
        Retrieve symbols from the specified file.

        This method should be implemented to retrieve symbols for the specific language.
        """
        raise NotImplementedError("The get_symbols method must be implemented in the subclass.")
    
    def get_definitions(self, file_path: str | Path, position):
        """
        Retrieve definitions from the specified file at the given position.

        This method should be implemented to retrieve definitions for the specific language.
        """
        raise NotImplementedError("The get_definitions method must be implemented in the subclass.")
    
    def get_references(self, file_path: str | Path, position):
        """
        Retrieve references from the specified file at the given position.

        This method should be implemented to retrieve references for the specific language.
        """
        raise NotImplementedError("The get_references method must be implemented in the subclass.") 