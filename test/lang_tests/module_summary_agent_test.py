import pytest
# from agent.module_summary_agent import ModuleSummaryAgent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

@pytest.fixture
def file_summary_agent():
    responses = [
        AIMessage(content="Summary for module 1..."),
        AIMessage(content="Summary for module 2...")]
    # return ModuleSummaryAgent(llm=GenericFakeChatModel(messages=iter(responses)))