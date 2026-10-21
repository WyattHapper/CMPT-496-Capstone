
from pathlib import Path

from lsp.base_client import LSPClient
from lsp_client.clients.pyright import PyrightClient


class PythonClient(LSPClient):
    """LSP adapter for Python using Pyright."""

    def __init__(self, workspace_path: str | Path):
        super().__init__(
            workspace_path=workspace_path,
            client_class=PyrightClient,
        )
