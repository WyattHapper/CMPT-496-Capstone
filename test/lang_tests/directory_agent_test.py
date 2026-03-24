import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
import pytest
from agent.directory_agent import DirectoryAgent
from agent.structured_output.directory_output import ContextAnalysisOutput
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from collections import deque
import os
from agent.structured_output.directory_output import DirectoryOutput, ContextAnalysisOutput

class FakeCollection:
    def __init__(self, documents, metadatas):
        self._documents = documents
        self._metadatas = metadatas

    def query(self, query_texts, n_results):
        return {
            "documents": [self._documents[:n_results]],
            "metadatas": [self._metadatas[:n_results]],
        }
    
class FakeStructuredLLM:
    def __init__(self, output):
        self.output = output

    def invoke(self, prompt):
        return self.output

class FakeLLMWithStructuredOutput:
    def __init__(self, output):
        self.output = output

    def with_structured_output(self, schema):
        return FakeStructuredLLM(self.output)

@pytest.fixture
def directory_agent():
    responses = [
        AIMessage(content="Summary for directory 1..."),
        AIMessage(content="Summary for directory 2..."),
        AIMessage(content="Summary for directory 3..."),
        AIMessage(content="Summary for directory 4...")]
    return DirectoryAgent(model=GenericFakeChatModel(messages=iter(responses)))

def test_crawler_node(directory_agent):
    current_dir = Path(__file__).parent
    test_codebase_path = str(current_dir / "TestCodebase")

    initial_state = {
        "directory_path": test_codebase_path,
        "directories": deque()
    }

    result = directory_agent.crawler_node(initial_state)

    assert "directories" in result
    assert result["total_number_of_directories"] == 4

    dirs = list(result["directories"])

    # ignored directories
    assert not any("bin" in d for d in dirs)
    assert not any("obj" in d for d in dirs)

    # paths are directories
    for d in dirs:
        assert Path(d).is_dir()

    # correct ordering
    depths = [d.count(os.sep) for d in dirs]
    assert depths == sorted(depths)

    # codebase name correct
    assert result["codebase_name"] == Path(test_codebase_path).name

    # container type
    assert isinstance(result["directories"], deque)

def test_retriever_node(directory_agent):
    root_dir = "/repo"
    current_dir = "/repo/src/parser"

    code_collection = FakeCollection(
        documents=[
            "def parse(): pass",
            "def unrelated(): pass",
        ],
        metadatas=[
            {
                "file": "src/parser/main.py",
                "container": "function",
                "name": "parse",
                "type": "function",
                "namespace": "src.parser.main",
                "start_line": 1,
                "end_line": 2,
            },
            {
                "file": "src/other/utils.py",
                "container": "function",
                "name": "unrelated",
                "type": "function",
                "namespace": "src.other.utils",
                "start_line": 1,
                "end_line": 2,
            },
        ],
    )

    summary_collection = FakeCollection(
        documents=[
            "Parser module handles parsing tokens into AST.",
            "Other module utility summary.",
        ],
        metadatas=[
            {
                "path": "src/parser/main.py",
                "type": "file",
                "name": "main.py",
                "parent": "src/parser",
            },
            {
                "path": "src/other/utils.py",
                "type": "file",
                "name": "utils.py",
                "parent": "src/other",
            },
        ],
    )

    state = {
        "directory_path": root_dir,
        "directories": deque([current_dir]),
        "code_context": [],
        "summary_context": [],
        "sufficient_code_context": False,
        "sufficient_summary_context": False,
        "codebase_k": 10,
        "file_summary_k": 10,
        "current_directory": current_dir,
        "codebase_name": "repo",
        "total_number_of_directories": 1,
        "code_collection": code_collection,
        "summary_collection": summary_collection,
    }

    result = directory_agent.retriever_node(state)

    assert result["current_directory"] == current_dir
    assert len(result["code_context"]) == 2
    assert len(result["summary_context"]) == 2

    # The first code item should be the in-directory one
    assert "File: src/parser/main.py" in result["code_context"][0]

    # The first summary item should be the in-directory one
    assert "Path: src/parser/main.py" in result["summary_context"][0]

def test_context_analyser_node_sufficient(directory_agent):
    directory_agent.llm = FakeLLMWithStructuredOutput(
        ContextAnalysisOutput(
            sufficient_code_context=True,
            sufficient_summary_context=True,
            recommended_codebase_k_increase=0,
            recommended_file_summary_k_increase=0,
        )
    )

    state = {
        "directory_path": "/repo",
        "directories": deque(["/repo/src/parser"]),
        "code_context": ["[CODE CHUNK]\nFile: src/parser/main.py\nContent:\ndef parse(): pass"],
        "summary_context": ["[SUMMARY NODE]\nPath: src/parser/main.py\nContent:\nParser summary"],
        "sufficient_code_context": False,
        "sufficient_summary_context": False,
        "codebase_k": 10,
        "file_summary_k": 10,
        "current_directory": "/repo/src/parser",
        "codebase_name": "repo",
        "total_number_of_directories": 1,
        "code_collection": None,
        "summary_collection": None,
    }

    result = directory_agent.context_analyser_node(state)

    assert result["sufficient_code_context"] is True
    assert result["sufficient_summary_context"] is True
    assert result["codebase_k"] == 10
    assert result["file_summary_k"] == 10

def test_summarizer_node(directory_agent):
    # Simulate the state after crawling
    state = {
        "current_directory": str(Path(__file__).parent / "TestCodebase" / "Shapes"),
        "directories": deque([
            str(Path(__file__).parent / "TestCodebase" / "Math"),
            str(Path(__file__).parent / "TestCodebase" / "Circles"),
            str(Path(__file__).parent / "TestCodebase")
        ]),
        "code_context": ["Test1", "Test2", "Test3", "Test4", "Test5"],
        "summary_context": ["Test1", "Test2", "Test3", "Test4", "Test5"],
        "sufficient_code_context": True,
        "sufficient_summary_context": True,
        "codebase_k": 50,
        "file_summary_k": 49
    }

    # simulate 1st summarizer_node call
    result1 = directory_agent.summarizer_node(state)
    # make sure that summarizer_node clears directory specific info after it is called
    assert "directory_summary" in result1
    assert result1["code_context"] == []
    assert result1["summary_context"] == []
    assert result1["sufficient_code_context"] is False
    assert result1["sufficient_summary_context"] is False
    assert result1["codebase_k"] == 10
    assert result1["file_summary_k"] == 10
    # make sure that directory summary did not get reset back to nothing
    assert result1["directory_summary"].purpose == "Summary for directory 1..."
    assert result1["directory_summary"].directory_path == str(Path(__file__).parent / "TestCodebase" / "Shapes")
    assert result1["directory_summary"].directory_name == "Shapes"

    # simulate graph advancing to next directory
    state["current_directory"] = state["directories"].popleft()

    # simulate 2nd summarizer_node call
    result2 = directory_agent.summarizer_node(state)
    # make sure that summarizer_node clears directory specific info after it is called
    assert "directory_summary" in result2
    assert result2["code_context"] == []
    assert result2["summary_context"] == []
    assert result2["sufficient_code_context"] is False
    assert result2["sufficient_summary_context"] is False
    assert result2["codebase_k"] == 10
    assert result2["file_summary_k"] == 10
    # make sure that directory summary did not get reset back to nothing
    assert result2["directory_summary"].purpose == "Summary for directory 2..."
    assert result2["directory_summary"].directory_path == str(Path(__file__).parent / "TestCodebase" / "Math")
    assert result2["directory_summary"].directory_name == "Math"

def test_writer_node(directory_agent, tmp_path):
    # creates a temporary directory 
    output_dir = tmp_path / "summaries"
    output_dir.mkdir()

    # simulate directory names
    directories = ["Shapes", "Math", "Circles"]

    for d in directories:
        # provide a dummy state for each directory
        state = {
            "output_directory": str(output_dir),
            "codebase_name": "repo",
            "directory_path": "/repo",
            "directories": deque([]),
            "directory_summary": DirectoryOutput(
                directory_name=d,
                directory_path=f"/repo/{d}",
                purpose=f"{d} utilities"
            )
        }
        directory_agent.writer_node(state)

    repo_dir = output_dir / "repo"
    # make sure that tmp_path/summaries/repo exists 
    assert repo_dir.exists()

    # check that there is at least one JSON file for each directory summary
    files = [f.name for f in repo_dir.iterdir() if f.suffix == ".json"] # gets all files from tmp_path/summaries/repo that end in .json
    for d in directories:
        assert any(d in f for f in files) # make sure that their is atleast one .json file for each of "Shapes", "Math", "Circles"

