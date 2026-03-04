import pytest
# from agent.directory_agent import DirectoryAgent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

@pytest.fixture
def directory_agent():
    responses = [
        AIMessage(content="Summary for directory 1..."),
        AIMessage(content="Summary for directory 2...")]
    # return DirectoryAgent(llm=GenericFakeChatModel(messages=iter(responses)))