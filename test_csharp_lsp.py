import asyncio
from pathlib import Path

from lsp_client import Client, LocalServer


CODEBASE = Path("/Users/ianayotte/Downloads/ConsoleTables-main")
SOLUTION = CODEBASE / "ConsoleTables.sln"
FILE = CODEBASE / "src/ConsoleTables/ConsoleTable.cs"


async def main():
    server = LocalServer(
        program="csharp-ls",
        args=["--solution", str(SOLUTION)],
        cwd=CODEBASE,
    )

    client = Client(
        server=server,
        workspace=CODEBASE,
    )

    async with client:
        print("LSP started!")

        content = FILE.read_text()

        await client.notify_text_document_opened(
            FILE,
            content,
        )

        print("File opened!")

        result = await client.request_document_symbol(FILE)

        print("Symbols:")
        print(result)


asyncio.run(main())