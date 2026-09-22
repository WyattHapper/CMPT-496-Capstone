"""
agent/crawl_config.py

Shared rules for which files and folders the pipeline looks at.

These used to be local variables inside two different crawler functions:
IGNORED_DIRS in directory_agent.crawler_node, and acceptable_extensions in
file_summary_agent.crawler_node. Only the directory crawler had a skip list,
so the file crawler walked into bin/, obj/, node_modules/ and .venv/ and paid
for one LLM call per generated or vendored file.

Keeping both lists here means the crawlers, and the token estimator that
predicts their cost, cannot disagree about what counts as source code.
"""

# File types the pipeline will summarize.
ACCEPTABLE_EXTENSIONS = {
    ".cs", ".py", ".md", ".js", ".ts",
    ".sh", ".bash", ".c", ".cpp", ".html", ".css",
}

# Folders that hold generated, vendored or tooling files rather than code a
# person wrote. May need extending as more target languages are supported.
IGNORED_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    "node_modules",
    "bin",
    "obj",
    ".venv",
    ".vscode",
    "NuSpecs",
    "NuSpec",
    "Debug",
}


def prune(dirs):
    """
    Drop ignored folders from an os.walk subdirectory list, in place.

    os.walk only skips a folder if its `dirs` list is mutated in place before
    the next iteration -- rebinding the name does nothing. Call as:

        for root, dirs, filenames in os.walk(path):
            prune(dirs)
    """
    dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
    return dirs
