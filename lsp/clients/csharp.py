"""
@file csharp.py
@brief C# language-specific LSP client.
"""

from pathlib import Path

from lsp.base_client import LSPClient

from lsp_client import Client  # Replace with the actual C# LSP client class
from lsp_client.server import DefaultServers
from lsp_client.server.local import LocalServer
from lsp_client.protocol.lang import LanguageConfig
from lsp_client.utils.types import lsp_type
from lsp_client.server.container import ContainerServer
from lsp_client.capability.request import WithRequestDefinition, WithRequestReferences, WithRequestDocumentSymbol

class CSharpLSPClient(Client, WithRequestDefinition, WithRequestReferences, WithRequestDocumentSymbol):
    """
    C# language-specific LSP client.

    Language-specific clients should primarily define which
    third-party LSP client/server implementation they use.
    Common LSP functionality is inherited from LSPClient.
    """

    def create_default_servers(self)-> DefaultServers:
        """
        Create the default servers for the C# LSP client.

        Returns:
            DefaultServers: The default servers for the C# LSP client.
        """
        # Implement the logic to create and return the default servers for C#
        return DefaultServers(
            local=LocalServer(program="csharp-ls"),
            container=ContainerServer(image="csharp-ls"),
            )  
    
     
    def get_language_config(self) -> LanguageConfig:
        """
        Get the language configuration for the C# LSP client.

        Returns:
            LanguageConfig: The language configuration for the C# LSP client.
        """
        # Implement the logic to return the language configuration for C#
        return LanguageConfig(
            kind = lsp_type.LanguageKind.CSharp,
            suffixes=[".cs"],
            project_files=["*.sln", "*.csproj"],
        )

    def check_server_compatibility(self, info) -> None:
        return 

class CSharpClient(LSPClient):
    """
    C# language-specific LSP client.

    Language-specific clients should primarily define which
    third-party LSP client/server implementation they use.
    Common LSP functionality is inherited from LSPClient.
    """

    def __init__(self, workspace_path: str | Path):
        super().__init__(
            workspace_path=workspace_path,
            client_class=CSharpLSPClient,
        )

