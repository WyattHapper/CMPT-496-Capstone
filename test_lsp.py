import asyncio
from pathlib import Path

from lsp.client import LSPClient


CODEBASE = Path("lsp_test").resolve()
MAIN_FILE = CODEBASE / "main.py"


async def main():
    print("Starting LSP...")

    async with LSPClient(CODEBASE) as lsp:
        print("LSP started!")

        file_content = MAIN_FILE.read_text()

        await lsp.open_file(
            MAIN_FILE,
            file_content
        )

        print("File opened!")

        # Test getting the definition of "greet"
        definitions = await lsp.get_definitions(
            MAIN_FILE,
            line=2,
            character=10
        )

        print("\nDEFINITIONS:")
        print(type(definitions))
        print(definitions)

        if definitions:
            print(type(definitions[0]))
            print(definitions[0])

        # Test finding references to "greet"
        references = await lsp.get_references(
            MAIN_FILE,
            line=2,
            character=10
        )

        print("\nREFERENCES:")
        print(type(references))
        print(references)

        if references:
            print(type(references[0]))
            print(references[0])


if __name__ == "__main__":
    asyncio.run(main())