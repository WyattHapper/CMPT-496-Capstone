from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI
import getpass
import os
from dotenv import load_dotenv

load_dotenv()

model = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    api_key=os.getenv("GOOGLE_API_KEY"))

with open("test/lang_tests/shapes_test.py", "r") as f:
    code = f.read()

messages = [
    ("system", "You are a helpful assistant that summarizes code."),
    ("user", f"Summarize the following code file: \n\n{code}")
]

response = model.invoke(messages)
print(response.text)