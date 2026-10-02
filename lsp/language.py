#TODO
# Some extensions are shared by multiple languages.
# For now, we assign a default language to ambiguous extensions.
# A future version can use file-content analysis or project configuration
# to determine the language more accurately.    
"""
    @file backend/lsp/language.py
    @brief Language detection based on file extension.
    @details This module provides a function to detect the programming language of a file based on its extension. It maintains mappings of file extensions and exact filenames to their corresponding languages. The detection logic first checks for exact filename matches, then falls back to checking the file extension. This allows for accurate language detection in most cases, while also providing a mechanism to handle ambiguous extensions.
"""

from pathlib import Path

LSP_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "go",
    "rust",
    "csharp",
}

NON_LSP_LANGUAGES = {
    "markdown",
    "html",
    "css",
    "sql",
    "yaml",
    "bash",
    "powershell",
}

SUPPORTED_LANGUAGES = LSP_LANGUAGES | NON_LSP_LANGUAGES

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",

    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "bash",
    ".bash": "bash",
    ".ps1": "powershell",
}

def detect_language(filename: str) -> str | None:
    """
    Detect language from a filename, checking exact-filename matches
    first, then falling back to extension.
    """
    path = Path(filename)

    if path.name in LANGUAGE_FILENAMES:
        return LANGUAGE_FILENAMES[path.name]

    extension = path.suffix.lower()

    return LANGUAGE_EXTENSIONS.get(extension)