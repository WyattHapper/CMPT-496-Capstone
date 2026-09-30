"""Utilities for constructing valid ChromaDB collection names."""

import re


def collection_name(codebase_name: str, collection_type: str) -> str:
    """Build a ChromaDB-safe collection name for a codebase."""
    prefix = re.sub(r"[^a-zA-Z0-9._-]+", "_", codebase_name).strip("._-")
    prefix = prefix or "codebase"
    suffix = f"_{collection_type}_db"
    return f"{prefix[:512 - len(suffix)]}{suffix}"