#!/usr/bin/env python3
"""Utility script to test Sheld QA LangGraph endpoint."""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


class SheldQAClient:
    """HTTP client for Sheld QA chat completions."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        api_key: str = "lg-sheld-qa-key-12345",
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
        )

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        stream: bool = False,
        max_tokens: Optional[int] = 200,
        user: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """Send a chat completion request and measure latency."""

        url = f"{self.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {"messages": messages, "stream": stream, **kwargs}

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if user is not None:
            payload["user"] = user

        try:
            start = time.time()
            response = self.session.post(url, json=payload)
            elapsed = time.time() - start
            response.raise_for_status()
            return response.json(), elapsed
        except requests.exceptions.RequestException as exc:  # pragma: no cover - debug helper
            print(f"Request failed: {exc}")
            if getattr(exc, "response", None) is not None:
                print(f"Response status: {exc.response.status_code}")
                print(f"Response text: {exc.response.text}")
            return None, 0.0

    def simple_chat(self, question: str, user: str = "sheld-qa-test") -> Tuple[Optional[Dict[str, Any]], float]:
        """Single-turn helper."""

        return self.chat_completion(messages=[{"role": "user", "content": question}], user=user)


def main() -> None:
    client = SheldQAClient()
    print("Sending Sheld QA request...")
    resp, elapsed = client.simple_chat("上海迪士尼酒店会员制度")
    if resp:
        print(f"Completed in {elapsed:.3f}s, response:")
        print(json.dumps(resp, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
