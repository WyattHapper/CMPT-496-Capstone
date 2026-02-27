import pytest
from agent.file_summary_agent import FileSummaryAgent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from collections import deque
import os
from pathlib import Path

@pytest.fixture
def file_summary_agent():
    responses = [
        AIMessage(content="Summary for file 1..."),
        AIMessage(content="Summary for file 2..."),
        AIMessage(content="Summary for file 3..."),
        AIMessage(content="Summary for file 4...")]
    return FileSummaryAgent(llm=GenericFakeChatModel(messages=iter(responses)))


def test_crawler_node(file_summary_agent):
    current_dir = Path(__file__).parent
    test_codebase_path = str(current_dir / "TestCodebase")

    initial_state = {
        "directory_path": test_codebase_path,
        "files": deque()
    }

    result = file_summary_agent.crawler_node(initial_state)
    
    # Check that crawler found two files, so excluded the .txt file in TestCodebase
    assert "files" in result
    assert result["total_number_of_files"] == 4


def test_summarizer_node(file_summary_agent):
    # Simulate the state after crawling, with two files to summarize
    state = {
        "files": deque([
            str(Path(__file__).parent / "TestCodebase" / "Shapes" / "shapes2.py"),
            str(Path(__file__).parent / "TestCodebase" / "Shapes" / "shapes.py"),
            str(Path(__file__).parent / "TestCodebase" / "Math" / "math2.py"),
            str(Path(__file__).parent / "TestCodebase" / "Math" / "math.py")
        ])
    }

    # Test summarization for the first file
    result1 = file_summary_agent.summarizer_node(state)
    assert "file_summary" in result1
    assert result1["current_file"] == "math.py"
    assert result1["file_summary"].summary == "Summary for file 1..."

    # Test summarization for the second file
    result2 = file_summary_agent.summarizer_node(state)
    assert "file_summary" in result2
    assert result2["current_file"] == "math2.py"
    assert result2["file_summary"].summary == "Summary for file 2..."


def test_full_graph(file_summary_agent):
    current_dir = Path(__file__).parent
    test_codebase_path = str(current_dir / "TestCodebase")

    # Run the full graph on the test codebase
    file_summary_agent.run(test_codebase_path)

    # Check that output files were created for both source code files
    output_dir = Path("./agent/file_summary_agent_output") / "TestCodebase"
    assert output_dir.exists()
    assert (output_dir / "math-py.json").exists()
    assert (output_dir / "shapes-py.json").exists()