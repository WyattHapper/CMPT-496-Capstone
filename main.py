"""
main.py

Backend entry point for the Codebase Analysis system.

This file exposes commands to external callers
(JavaScript application, API layer, Electron, etc.)
through the CommandDispatcher.
"""

import sys

sys.stdout.reconfigure(
    encoding="utf-8",
    line_buffering=True
)


from backend.dispatcher import CommandDispatcher
from backend.preview_collections import CollectionPreview



# ---------------------------------------------------------
# Initialize backend services
# ---------------------------------------------------------

dispatcher = CommandDispatcher()

preview_service = CollectionPreview()



# ---------------------------------------------------------
# Command execution entrypoint
# ---------------------------------------------------------

def execute_command(command: str, **kwargs):
    """
    Execute a backend command.

    Example:

        execute_command(
            "build_database",
            codebase="C:/project"
        )

    """

    return dispatcher.dispatch(
        command,
        **kwargs
    )



# ---------------------------------------------------------
# Collection preview entrypoint
# ---------------------------------------------------------

def preview_command(action: str, **kwargs):
    """
    Execute collection preview operations.

    Example:

        preview_command(
            "list",
            db_type="summary"
        )

    """

    if action == "list":

        return preview_service.list_collections(
            kwargs["db_type"]
        )


    elif action == "preview":

        return preview_service.preview_collection(
            kwargs["collection_name"],
            kwargs.get("limit", 5)
        )


    elif action == "all":

        return preview_service.preview_collections(
            kwargs["db_type"],
            kwargs.get("limit", 5)
        )


    else:

        return {
            "success": False,
            "error": (
                f"Unknown preview action: {action}"
            )
        }



# ---------------------------------------------------------
# Local testing
# ---------------------------------------------------------

if __name__ == "__main__":


    result = execute_command(
        "full_pipeline",
        codebase="/Users/ianayotte/Downloads/ConsoleTables-main"
    )


    print(result)