import os
import json
import time
import requests

import config


class LLMProvider:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")

        self.api_key = api_key
        self.max_requests: int = int(os.getenv("MAX_LLM_REQUESTS", 40))
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1/chat/completions")
        self.request_count = 0
        self.timeout = getattr(config, "LLM_READ_TIMEOUT", 120)
        self.retry_attempts = getattr(config, "LLM_RETRY_ATTEMPTS", 2)
        self.retry_delay = getattr(config, "LLM_RETRY_DELAY", 2.0)
        self.session: requests.Session = requests.Session()

    def _post_with_retry(self, url: str, payload: dict, headers: dict) -> requests.Response:
        """POST with a small retry loop on read timeout and connection errors."""
        last_exc = None
        for attempt in range(self.retry_attempts):
            try:
                return self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=(10, self.timeout),
                )
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
        raise last_exc

    def generate(self, messages: list[dict], model: str = "deepseek-chat", max_tokens: int = 2000, temperature: float = 0.7) -> str:
        if (
            not isinstance(messages, list)
            or not messages
            or not all(isinstance(m, dict) for m in messages)
        ):
            raise ValueError("messages must be a non-empty list of dicts")

        if self.request_count >= self.max_requests:
            raise RuntimeError(f"LLM request limit reached ({self.max_requests}). Consider increasing MAX_LLM_REQUESTS in .env.")

        self.request_count += 1

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        resp = self._post_with_retry(self.base_url, payload, headers)

        if resp.status_code != 200:
            raise ConnectionError(f"DeepSeek API returned status {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON response from DeepSeek API.")

        try:
            content = data["choices"][0]["message"]["content"]
            return content
        except (KeyError, IndexError, TypeError):
            raise ValueError("Invalid response structure from DeepSeek API.")

    def get_usage(self) -> dict:
        return {
            "total_requests": self.request_count,
            "max_requests": self.max_requests
        }