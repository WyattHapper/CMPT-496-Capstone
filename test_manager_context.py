import asyncio
from pathlib import Path

from lsp.manager import LSPManager


CODEBASE = Path(
    "/Users/ianayotte/Downloads/ConsoleTables-main"
)


async def main():

    print("Creating LSP manager...")

    async with LSPManager(CODEBASE) as manager:

        print("LSP manager started!")

        print(f"Detected languages: {manager.languages}")

        print(f"Active clients: {list(manager.clients.keys())}")

        client = manager.clients["csharp"]

        print(f"C# client: {type(client).__name__}")

        test_file = (
            CODEBASE
            / "src"
            / "ConsoleTables"
            / "ConsoleTable.cs"
        )

        language = manager.get_language(test_file)
        file_client = manager.get_client(test_file)

        print(f"File language: {language}")
        print(f"File client: {type(file_client).__name__}")

        context = await manager.get_file_context(test_file)

        print(f"Context file: {context.file_path}")
        print(f"Context language: {context.language}")
        print(f"Top-level symbols: {len(context.symbols)}")

        for symbol in context.symbols:
            print(f"Symbol: {symbol.name}")

            for child in symbol.children:
                print(f"  Child: {child.name}")


    print("LSP manager stopped!")


if __name__ == "__main__":
    asyncio.run(main())