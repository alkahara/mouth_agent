#!/usr/bin/env python3
import requests
import json
import time


def make_chat_request():
    """Make a chat completion request to the API"""
    
    # API endpoint
    url = "http://127.0.0.1:8080/v1/chat/completions"
    
    # Headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer lg-mouth-cavity-key-12345"
    }
    
    # Request payload
    payload = {
        "messages": [{"role": "user", "content": "口腔护理"}],
        "stream": False,
        "max_tokens": 200,
        "user": "9999"
    }
    
    try:
        # Record start time
        start_time = time.time()
        
        # Make the POST request
        response = requests.post(url, headers=headers, json=payload)
        
        # Record end time
        end_time = time.time()
        
        # Calculate elapsed time
        elapsed_time = end_time - start_time
        
        # Check if request was successful
        response.raise_for_status()
        
        # Print response and timing information
        print(f"Request completed in {elapsed_time:.4f} seconds")
        print("Status Code:", response.status_code)
        print("Response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return None


if __name__ == "__main__":
    make_chat_request()
