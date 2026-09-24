from pathlib import Path

from lsp.manager import LSPManager
from lsp.language import detect_language


CODEBASE = Path("/Users/ianayotte/Downloads/ConsoleTables-main")

MAIN_FILE = CODEBASE / "src/ConsoleTables/ConsoleTable.cs"


print("MAIN_FILE:", MAIN_FILE)
print("Detected language:", detect_language(MAIN_FILE))

manager = LSPManager(CODEBASE)

print("\nLanguages detected:")
for language in sorted(manager.languages):
    print("-", language)