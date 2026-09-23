import asyncio
from pathlib import Path

from lsp.manager import LSPManager
from lsp.models import Definition, Reference


CODEBASE = Path("lsp_test").resolve()
MAIN_FILE = CODEBASE / "main.py"


async def main():

    manager = LSPManager(MAIN_FILE)

    print("Language:", manager.language)
    print("Client class:", manager.client_class)

    async with manager.create_client(CODEBASE) as lsp:

        print("LSP started!")

        file_content = MAIN_FILE.read_text()

        await lsp.open_file(
            MAIN_FILE,
            file_content
        )

        print("File opened!")

        definitions = await lsp.get_definitions(
            MAIN_FILE,
            line=2,
            character=10
        )

        references = await lsp.get_references(
            MAIN_FILE,
            line=2,
            character=10
        )

        print("\nDEFINITIONS:")
        print(definitions)

        print("\nREFERENCES:")
        print(references)

        assert definitions
        assert references

        assert isinstance(
            definitions[0],
            Definition
        )

        assert isinstance(
            references[0],
            Reference
        )

        print("\n✓ Manager → LSPClient test passed!")


if __name__ == "__main__":
    asyncio.run(main())