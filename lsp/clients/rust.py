
from pathlib import Path

from lsp.base_client import LSPClient
from lsp_client.clients.rust_analyzer import RustAnalyzerClient


class RustClient(LSPClient):
    """LSP adapter for go using goplsclient."""

    def __init__(self, workspace_path: str | Path):
        super().__init__(
            workspace_path=workspace_path,
            client_class=RustAnalyzerClient,
        )
