import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.1-8b-instruct:free')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Validate API key
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set in .env file")

# Test request
headers = {
    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
    'Content-Type': 'application/json'
}

prompt = """
Analyze the following text (first 25 lines of a document) and determine if it is a resume. A resume typically includes sections like personal information (name, contact details), education, work experience, skills, or job titles. Return a JSON response with a single field 'is_resume' set to true or false.

Text:
Test document content
"""

payload = {
    'model': OPENROUTER_MODEL,
    'messages': [{'role': 'user', 'content': prompt}],
    'response_format': {'type': 'json_object'}
}

try:
    print("Sending request:", json.dumps(payload, indent=2))
    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=10)
    print(f"Status Code: {response}")
    print(f"Headers: {json.dumps(dict(response.headers), indent=2)}")
    print(f"Response Body: {response.text[:1000]}...")
    if response.headers.get('content-type', '').startswith('application/json'):
        result = response.json()['choices'][0]['message']['content']
        print(f"Parsed Result: {result}")
    else:
        print("Non-JSON response received")
except Exception as e:
    print(f"Error: {str(e)}")