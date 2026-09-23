import asyncio
from pathlib import Path

from lsp.client import LSPClient
from lsp.models import Definition, Reference


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

        # --------------------------------------------------
        # Test definitions
        # --------------------------------------------------

        definitions = await lsp.get_definitions(
            MAIN_FILE,
            line=2,
            character=10
        )

        print("\nDEFINITIONS:")
        print(definitions)

        if definitions:
            print("Definition type:")
            print(type(definitions[0]))

            assert isinstance(definitions[0], Definition)

            print("✓ Definition is a Pydantic Definition model")

            print("\nDefinition location:")
            print(definitions[0].location)

        # --------------------------------------------------
        # Test references
        # --------------------------------------------------

        references = await lsp.get_references(
            MAIN_FILE,
            line=2,
            character=10
        )

        print("\nREFERENCES:")
        print(references)

        if references:
            print("Reference type:")
            print(type(references[0]))

            assert isinstance(references[0], Reference)

            print("✓ Reference is a Pydantic Reference model")

            print("\nReference locations:")

            for reference in references:
                print(reference.location)

        # --------------------------------------------------
        # Basic validation
        # --------------------------------------------------

        assert definitions
        assert references

        print("\n✓ LSP client test passed!")


if __name__ == "__main__":
    asyncio.run(main())