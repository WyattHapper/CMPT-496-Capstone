# CMPT-496-Capstone

## Purpose
This repository contains a tool which can be used to perform analysis of large codebases. The tool creates as output:
- Summaries of each file
- Code structure information for each file, including PlantUML
- Summaries of the contents of each directory
- A summary of the entire repository
- A list of business rules extracted from the codebase

This is all completed using LangGraph, with an LLM acting as the generator of outputs. There is included a command line tool for running the project, in main.py.

## Notes
- This tool is currently able to parse codebases written in C# or Javascript for the vector store component. Other languages are not supported.
- The system defaults to using Gemini 3 Flash, given a valid API key in a .env file. Your API key should be titled "GOOGLE_API_KEY" in your .env file
- The system is mostly set up to support the use of other models. Additional steps required: Either the agents should be instantiated and run manually, by passing in the desired model, or main.py should be modified slightly to do so
- When running the tool, a filepath to the target codebase is needed. Use relative paths
- It is recommended to store the target codebase in a directory in the root of the project called "targetCodebases", as this directory is already included in the .gitignore

## Requirements

**Python 3.13+** is required for this project.

Download Python: [https://www.python.org/downloads/](https://www.python.org/downloads/)

## Setup Instructions

1. **Create a virtual environment:**
   ```powershell
   python -m venv .venv
   ```

2. **Activate the virtual environment:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Run the program:**
   ```powershell
   python test.py
   ```

## Deactivate Virtual Environment
```powershell
deactivate
```

## Convert JSON summaries to Markdown

```powershell
# default: reads `agent/file_summary_agent_output` and writes to `<input-dir>/markdown`
python -m utils.json_to_markdown

# print to stdout for quick verification
python -m utils.json_to_markdown --stdout

# specify input/output and avoid overwriting
python -m utils.json_to_markdown --input-dir agent/file_summary_agent_output --output-dir ./markdown --no-overwrite
```

Flags:
- `--input-dir`: directory containing JSON summary files (default: `agent/file_summary_agent_output`)
- `--output-dir`: directory to write markdown files (default: `<input-dir>/markdown`)
- `--stdout`: print results instead of writing files
- `--overwrite` / `--no-overwrite`: controls replacing existing `.md` files (default: overwrite enabled)
- `--ext`: file extension to search for (default: `.json`)

Notes:
- Run the command from the project root so the default input path resolves correctly.
