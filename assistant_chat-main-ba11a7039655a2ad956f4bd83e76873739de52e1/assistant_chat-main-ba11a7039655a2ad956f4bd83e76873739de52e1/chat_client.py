#!/usr/bin/env python3
import requests
import json
import time
from typing import List, Dict, Any, Optional, Tuple


class ChatClient:
    """A client for making chat completion requests"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8080", api_key: str = "lg-disney-key-12345"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        })
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        max_tokens: Optional[int] = 200,
        user: Optional[str] = None,
        thread_id: Optional[str] = None,
        **kwargs
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Make a chat completion request
        
        Args:
            messages: List of message objects with 'role' and 'content'
            stream: Whether to stream the response
            max_tokens: Maximum number of tokens to generate
            user: User identifier
            thread_id: UUID for session management (used for mouth_v2 agent)
            **kwargs: Additional parameters to pass to the API (e.g., debug_mode)
        
        Returns:
            Tuple containing:
            - Response JSON or None if failed
            - Time taken for the request in seconds
        """
        url = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "messages": messages,
            "stream": stream,
            **kwargs
        }

        debug_flag = payload.get("debug_mode")
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if user is not None:
            payload["user"] = user
        if thread_id is not None:
            payload["thread_id"] = thread_id
        
        try:
            # Record start time
            start_time = time.time()
            print(
                f"[ChatClient] POST {url} (user={user}, thread_id={thread_id}, stream={stream}, debug_mode={debug_flag}, max_tokens={payload.get('max_tokens')})"
            )

            # Make the request
            response = self.session.post(url, json=payload, timeout=(3.05, 600))
            
            # Record end time
            end_time = time.time()
            
            # Calculate elapsed time
            elapsed_time = end_time - start_time
            
            response.raise_for_status()
            return response.json(), elapsed_time
            
        except requests.exceptions.RequestException as e:
            print(f"[ChatClient] Request failed: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"[ChatClient] Response status: {e.response.status_code}")
            return None, 0.0
    
    def simple_chat(
        self,
        content: str,
        user: str = "9999",
        debug_mode: Optional[bool] = None,
        thread_id: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """Simple chat with a single user message."""
        messages = [{"role": "user", "content": content}]
        extra: Dict[str, Any] = {}
        if debug_mode is not None:
            extra["debug_mode"] = debug_mode
        return self.chat_completion(messages=messages, user=user, thread_id=thread_id, **extra)


def main():
    """Example usage"""
    client = ChatClient()
    
    # Original request
    print("Sending simple chat request...")
    response, elapsed_time = client.simple_chat("迪士尼年卡有什么优惠")
    
    if response:
        print(f"Request completed in {elapsed_time:.4f} seconds")
        print("Response:")
        print(json.dumps(response, indent=2, ensure_ascii=False))
    
    # Example with conversation
    messages = [
        {"role": "user", "content": "迪士尼年卡有什么优惠"},
        {"role": "assistant", "content": "迪士尼年卡有以下优惠..."},
        {"role": "user", "content": "价格是多少？"}
    ]
    
    print("\nSending conversation request...")
    response, elapsed_time = client.chat_completion(
        messages=messages,
        max_tokens=300,
        user="9999"
    )
    
    if response:
        print(f"Request completed in {elapsed_time:.4f} seconds")
        print("Conversation Response:")
        print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
