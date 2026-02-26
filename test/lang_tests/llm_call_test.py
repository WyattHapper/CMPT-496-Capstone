"""
@file llm_call_test.py
@brief Test file for making LLM calls to Google Gemini models using langchain and langchain_google_genai.
@details This script demonstrates how to set up and use the ChatGoogleGenerativeAI model from the langchain_google_genai library
to summarize a code file. It loads the API key from an environment variable, reads a code file, and sends it as a prompt to the model for summarization.
"""

from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv

load_dotenv()

# Model instantiation
model = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    api_key=os.getenv("GOOGLE_API_KEY"))

# Read the code file to be summarized
with open("test/lang_tests/TestCodebase/shapes_test.py", "r") as f:
    code = f.read()

# Prepare the messages for the model
messages = [
    ("system", "You are a helpful assistant that summarizes code."),
    ("user", f"Summarize the following code file: \n\n{code}")
]

# Invoke the model and print the response
response = model.invoke(messages)
print(response.text)