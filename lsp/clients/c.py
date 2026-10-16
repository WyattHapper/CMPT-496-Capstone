"""
@file c.py
@brief C language-specific LSP client.
"""

from pathlib import Path

from lsp.base_client import LSPClient

from lsp_client import Client  
from lsp_client.server import DefaultServers
from lsp_client.server.local import LocalServer
from lsp_client.protocol.lang import LanguageConfig
from lsp_client.utils.types import lsp_type
from lsp_client.server.container import ContainerServer
from lsp_client.capability.request import WithRequestDefinition, WithRequestReferences, WithRequestDocumentSymbol

class CLSPCLient(Client, WithRequestDefinition, WithRequestReferences, WithRequestDocumentSymbol):

    """
    C specific LSP Client
    """
    def create_default_servers(self):
        return DefaultServers(local=LocalServer(program="clangd"), container=ContainerServer(image="clangd"))
    
    def get_language_config(self):
        return LanguageConfig(kind=lsp_type.LanguageKind.C,suffixes=[".c", ".h"], project_files=["compile_commands.json",
                "compile_flags.txt",])
    
    def check_server_compatibility(self, info):
        return super().check_server_compatibility(info)
    

class CClient(LSPClient):
    """
    C language specific client
    """

    def __init__(self, workspace_path):
        super().__init__(workspace_path = workspace_path, client_class = CLSPCLient)