import pytest
from agent.directory_agent import DirectoryAgent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from collections import deque
from pathlib import Path

@pytest.fixture
def directory_agent():
    responses = [
        AIMessage(content="Summary for directory 1..."),
        AIMessage(content="Summary for directory 2...")]
    return DirectoryAgent(model=GenericFakeChatModel(messages=iter(responses)))

def test_crawler_node(directory_agent):
    current_dir = Path(__file__).parent
    test_codebase_path = str(current_dir / "TestCodebase")

    initial_state = {
        "directory_path": test_codebase_path,
        "files": deque()
    }

    result = directory_agent.crawler_node(initial_state)
    
    # Check that crawler found 5 dirs, so excluded the obj, bin, .vscode in TestCodebase
    assert "directories" in result
    assert result["total_number_of_directories"] == 5