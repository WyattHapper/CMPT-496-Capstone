import asyncio
from pathlib import Path

from lsp.clients.csharp import CSharpClient
from lsp.context import FileContext


CODEBASE = Path(
    "/Users/ianayotte/Downloads/ConsoleTables-main"
)

FILE = (
    CODEBASE
    / "src"
    / "ConsoleTables"
    / "ConsoleTable.cs"
)


async def main():
    print("Starting C# LSP...")

    async with CSharpClient(CODEBASE) as client:
        print("C# LSP started!")

        # Read the source file
        content = FILE.read_text()

        # Open the file in the language server
        await client.open_file(FILE, content)

        print("File opened!")

        # Find the ConsoleTable class declaration
        lines = content.splitlines()

        line = next(
            i
            for i, text in enumerate(lines)
            if "public class ConsoleTable" in text
        )

        character = lines[line].index("ConsoleTable")

        print(
            f"Testing definition at "
            f"line={line}, character={character}"
        )

        # Get definition information
        definitions = await client.get_definitions(
            FILE,
            line=line,
            character=character
        )

        # Get reference information
        references = await client.get_references(
            FILE,
            line=line,
            character=character
        )

        # Get document symbols
        symbols = await client.get_document_symbols(FILE)

        # Build language-independent file context
        context = FileContext(
            file_path=FILE,
            language="csharp",
            symbols=symbols,
            definitions=definitions,
            references=references,
        )

        # Display a concise summary of the context
        print("\nFile Context:")
        print(f"File: {context.file_path}")
        print(f"Language: {context.language}")
        print(f"Top-level symbols: {len(context.symbols)}")
        print(f"Definitions: {len(context.definitions)}")
        print(f"References: {len(context.references)}")

    print("\nC# LSP stopped!")

    from lsp.language import detect_language

    print(detect_language("ConsoleTable.cs"))
    print(detect_language("example.py"))
    print(detect_language("main.cpp"))


if __name__ == "__main__":
    asyncio.run(main())