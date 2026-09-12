import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from llm_provider import LLMProvider


class TestLLMProviderRetry(unittest.TestCase):

    def setUp(self):
        self._original_key = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "test-key"
        self.provider = LLMProvider()
        self.messages = [{"role": "user", "content": "hi"}]

    def tearDown(self):
        if self._original_key is None:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        else:
            os.environ["DEEPSEEK_API_KEY"] = self._original_key

    def _ok_response(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": "hello world"}}]
        }
        return resp

    @patch("time.sleep", return_value=None)
    def test_successful_post_no_retry(self, mock_sleep):
        ok = self._ok_response()
        with patch.object(self.provider.session, "post", return_value=ok) as mock_post:
            result = self.provider.generate(self.messages)

        self.assertEqual(result, "hello world")
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("time.sleep", return_value=None)
    def test_read_timeout_triggers_retry_and_succeeds(self, mock_sleep):
        ok = self._ok_response()
        side_effects = [requests.exceptions.ReadTimeout("boom"), ok]
        with patch.object(self.provider.session, "post", side_effect=side_effects) as mock_post:
            result = self.provider.generate(self.messages)

        self.assertEqual(result, "hello world")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(self.provider.retry_delay)

    @patch("time.sleep", return_value=None)
    def test_two_timeouts_raise_last_exception(self, mock_sleep):
        with patch.object(
            self.provider.session,
            "post",
            side_effect=requests.exceptions.ReadTimeout("always down"),
        ) as mock_post:
            with self.assertRaises(requests.exceptions.ReadTimeout):
                self.provider.generate(self.messages)

        self.assertEqual(mock_post.call_count, self.provider.retry_attempts)

    @patch("time.sleep", return_value=None)
    def test_connection_error_triggers_retry(self, mock_sleep):
        ok = self._ok_response()
        side_effects = [requests.exceptions.ConnectionError("net down"), ok]
        with patch.object(self.provider.session, "post", side_effect=side_effects) as mock_post:
            result = self.provider.generate(self.messages)

        self.assertEqual(result, "hello world")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(self.provider.retry_delay)

    @patch("time.sleep", return_value=None)
    def test_http_error_not_retried(self, mock_sleep):
        bad = MagicMock()
        bad.status_code = 400
        bad.text = "bad request"
        with patch.object(self.provider.session, "post", return_value=bad) as mock_post:
            with self.assertRaises(ConnectionError):
                self.provider.generate(self.messages)

        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()