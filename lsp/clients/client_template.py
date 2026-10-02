"""
@file client_template.py
@brief Template for adding a language-specific LSP client.
"""

from pathlib import Path

from lsp.base_client import LSPClient

#add import for the client

class LanguageClientTemplate(LSPClient):
    """
    Template for a language-specific LSP client.

    Language-specific clients should primarily define which
    third-party LSP client/server implementation they use.
    Common LSP functionality is inherited from LSPClient.
    """

    CLIENT_CLASS = None

    def __init__(self, workspace_path: str | Path):
        super().__init__(
            workspace_path=workspace_path,
            client_class=self.CLIENT_CLASS,
        )

    # class methods go in here