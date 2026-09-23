from pathlib import Path

from lsp.manager import LSPManager
from lsp_client import PyrightClient


FILE = Path("lsp_test/main.py")

manager = LSPManager(FILE)

print("File:", manager.file_path)
print("Language:", manager.language)
print("Client:", manager.client)

assert manager.language == "python"
assert manager.client == PyrightClient

print("\n✓ LSP manager test passed!")