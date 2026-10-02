from pathlib import Path

from lsp.manager import LSPManager


CODEBASE = Path(
    "/Users/ianayotte/Downloads/ConsoleTables-main"
)

FILE = (
    CODEBASE
    / "src"
    / "ConsoleTables"
    / "ConsoleTable.cs"
)


manager = LSPManager(CODEBASE)

language = manager.get_language(FILE)

print(f"Language: {language}")

client_class = manager.get_client_class(language)

print(f"Client: {client_class.__name__}")

client = manager.create_client(language)

print(f"Client instance: {type(client).__name__}")