'''
PURPOSE: Test file for using Google API keys

NOTE: .env file must have --> GEMINI_API_KEY=<API key from google website>

HOW TO RUN:
    option 1 --> use the run button in top corner
    option 2 --> python .\apiTest.py 
'''

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

# will print true if key is setup properly
print("Key loaded:", os.getenv("GEMINI_API_KEY") is not None)


# The code below will use tokens and part of the rate limits
# Uncomment below and it will spit out like 5 words when ran

#client = genai.Client()
#response = client.models.generate_content(
#    model="gemini-2.5-flash",
#    contents="Explain how AI works in a few words"
#)
#print(response.text)
