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

LANGUAGE_EXTENSIONS = {
    # Systems / compiled
    ".c": "c",
    ".h": "c",              # ambiguous with C++, resolved by filename/content if needed
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".swift": "swift",
    ".m": "objective-c",    # ambiguous with MATLAB
    ".mm": "objective-c",

    # JVM
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".groovy": "groovy",
    ".clj": "clojure",

    # Web / scripting
    ".py": "python",
    ".rb": "ruby",
    ".php": "php",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".pl": "perl",
    ".lua": "lua",

    # .NET
    ".cs": "csharp",
    ".fs": "fsharp",
    ".vb": "vbnet",

    # Functional
    ".hs": "haskell",
    ".ml": "ocaml",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",

    # Data / scientific
    ".r": "r",
    ".jl": "julia",
    ".sql": "sql",

    # Shell / config / infra
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".ps1": "powershell",
    ".tf": "terraform",
    ".yaml": "yaml",
    ".yml": "yaml",

    # Mobile
    ".dart": "dart",

    # Other
    ".zig": "zig",
    ".nim": "nim",
    ".sol": "solidity",
}

# Exact, case-sensitive filenames with no (or a non-signaling) extension.
LANGUAGE_FILENAMES = {
    "Dockerfile": "dockerfile",
    "Makefile": "makefile",
    "GNUmakefile": "makefile",
    "Rakefile": "ruby",
    "Gemfile": "ruby",
    "Vagrantfile": "ruby",
    "Podfile": "ruby",
    "Jenkinsfile": "groovy",
    "BUILD": "starlark",       # Bazel
    "BUILD.bazel": "starlark",
    "WORKSPACE": "starlark",
    "CMakeLists.txt": "cmake",
    "go.mod": "go",
    "go.sum": "go",
    ".bashrc": "bash",
    ".zshrc": "bash",
    ".profile": "bash",
    ".gitignore": "gitignore",
    ".editorconfig": "editorconfig",
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