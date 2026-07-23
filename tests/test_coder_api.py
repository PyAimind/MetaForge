import os, sys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_provider import LLMProvider

provider = LLMProvider()
model = os.getenv("LLM_CODER_MODEL", "deepseek/deepseek-chat-v3.1")
print(f"Testing with model: {model}")
try:
    resp = provider.generate(
        [{"role": "user", "content": "Write a simple Python function that returns the number 42. Return ONLY the code, no explanation."}],
        model=model,
        max_tokens=50,
        temperature=0
    )
    print(f"SUCCESS: {resp[:100]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")