import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock
from llm_provider import LLMProvider

os.environ["DEEPSEEK_API_KEY"] = "test-key"

with patch('llm_provider.requests.Session.post') as mock_post:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
    mock_post.return_value = mock_response
    provider = LLMProvider()
    result = provider.generate([{"role": "user", "content": "Hi"}], model="deepseek/deepseek-chat-v3.1")
    assert result == "OK"
    usage = provider.get_usage()
    assert usage["total_requests"] == 1
    assert usage["max_requests"] == 40

orig_key = os.environ["DEEPSEEK_API_KEY"]
os.environ["DEEPSEEK_API_KEY"] = ""
try:
    LLMProvider()
    assert False
except ValueError as e:
    assert str(e) == "DEEPSEEK_API_KEY not found in environment variables"
os.environ["DEEPSEEK_API_KEY"] = orig_key

provider = LLMProvider()
try:
    provider.generate([])
    assert False
except ValueError as e:
    assert "must be a non-empty list" in str(e)

provider = LLMProvider()
provider.request_count = provider.max_requests
try:
    provider.generate([{"role": "user", "content": "test"}])
    assert False
except RuntimeError as e:
    assert "LLM request limit reached" in str(e)

with patch('llm_provider.requests.Session.post') as mock_post:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"invalid": "structure"}
    mock_post.return_value = mock_response
    provider = LLMProvider()
    try:
        provider.generate([{"role": "user", "content": "test"}])
        assert False
    except ValueError as e:
        assert "Invalid response structure" in str(e)

with patch('llm_provider.requests.Session.post') as mock_post:
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server Error"
    mock_post.return_value = mock_response
    provider = LLMProvider()
    try:
        provider.generate([{"role": "user", "content": "test"}])
        assert False
    except ConnectionError as e:
        assert "500" in str(e)

print("PHASE 8 UNIT TESTS PASSED")