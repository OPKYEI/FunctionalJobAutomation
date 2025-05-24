# modules/ai/free_ai_client.py

import json
from typing import List, Dict, Any, Optional, Tuple
import re
from src.utilities.proxies import ProxyRotator

# Global proxy rotator
proxy_rotator = ProxyRotator()

# GPT model candidates in order of preference  
GPT_MODEL_CANDIDATES = [
    "gpt-3.5-turbo", 
    "claude-3-haiku-20240307",
    "deepseek-chat",
    "gemini-pro"
]

def get_free_ai_client():
    """Initialize and return a g4f client that can access models for free"""
    try:
        from g4f.client import Client
        return Client()
    except ImportError:
        print("g4f package not installed. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "g4f"])
        from g4f.client import Client
        return Client()

def free_ai_completion(prompt: str, model_candidates=None):
    """Send a prompt to free AI models with proxy rotation and fallbacks"""
    from g4f.client import Client
    
    if model_candidates is None:
        model_candidates = GPT_MODEL_CANDIDATES
    
    for model_name in model_candidates:
        for attempt in (1, 2):  # proxy, then rotate proxy
            try:
                client = Client(proxies=proxy_rotator.get_proxy())
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
                print(f"success with {model_name} via proxy")
                return response.choices[0].message.content
            except Exception as e:
                print(f"Attempt {attempt} with {model_name} failed: {e}")
                proxy_rotator.remove_current_proxy()

        # last-ditch: same model without proxy
        try:
            client = Client()
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            print(f"success with {model_name} (no proxy)")
            return response.choices[0].message.content
        except Exception:
            # move to next model in palette
            continue
    
    # If all attempts fail
    print("All model attempts failed - try updating model candidates")
    return "Error: Unable to get response from any AI model"

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Extract JSON content from text that might contain other content"""
    try:
        # Handle code block format if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        # Find JSON object within text if not properly formatted
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        if start_idx >= 0 and end_idx > start_idx:
            text = text[start_idx:end_idx]
            
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON: {text}")
        return {}