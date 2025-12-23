import requests
import re
import time
import random
import json


class LLMClient:
    """A client to interact with the university's Ollama instance.

    Simple wrapper that exposes a `generate_code(prompt)` method. It maps a
    text response to a Python code block (```python ... ```) when present.
    """

    def __init__(
        self, 
        base_url: str = "http://rhaegal.dimis.fim.uni-passau.de:15343",
        model_name: str = "deepseek-coder-v2:16b"
    ):
        """Initialize Ollama client.
        
        Args:
            base_url: Base URL of the Ollama instance
            model_name: Model to use (default: devstral:24b - Mistral's latest code-specialized model)
        """
        self.base_url = base_url.rstrip('/')
        self.model = model_name
        self.generate_endpoint = f"{self.base_url}/api/generate"

    def generate_code(self, prompt: str) -> str:
        """Generate text and return the Python code block (or plain text).

        Retries on network/server errors with exponential backoff + jitter.
        Returns a sentinel string when retries are exhausted or on unrecoverable errors.
        """
        attempts = 0
        base_backoff = 2  # Start at 2 seconds
        max_attempts = 3  # Fewer retries since this is a local instance
        
        while attempts < max_attempts:
            try:
                # Prepare request payload
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False  # Get complete response at once
                }
                
                # Make request to Ollama API
                response = requests.post(
                    self.generate_endpoint,
                    json=payload,
                    timeout=120  # 2 minute timeout for generation
                )
                
                # Check for HTTP errors
                if response.status_code != 200:
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}: {response.text}"
                    )
                
                # Parse response
                result = response.json()
                text = result.get("response", "")
                
                # Extract Python code block if present - handle multiple formats
                # Try with language specifier first
                match = re.search(r"```python\s*\n([\s\S]*?)```", text)
                if match:
                    return match.group(1).strip()
                
                # Try without language specifier
                match = re.search(r"```\s*\n([\s\S]*?)```", text)
                if match:
                    return match.group(1).strip()
                
                # No code blocks found, return as-is
                return text.strip()
            
            except requests.exceptions.Timeout:
                attempts += 1
                print(f"\n[TIMEOUT] Timeout error (Attempt {attempts}/{max_attempts})")
                if attempts >= max_attempts:
                    print(f"Max retries ({max_attempts}) exhausted.")
                    return "# LLM error: timeout"
                
                # Exponential backoff with jitter
                exponential_wait = base_backoff * (2 ** (attempts - 1))
                jitter = random.uniform(0, 1)
                wait_time = min(exponential_wait + jitter, 30)
                
                print(f"[WAIT] Waiting {wait_time:.2f} seconds before retry...")
                time.sleep(wait_time)
            
            except requests.exceptions.RequestException as e:
                attempts += 1
                print(f"\n{'-'*70}")
                print(f"LLM REQUEST ERROR (Attempt {attempts}/{max_attempts})")
                print(f"{'-'*70}")
                print(f"Error Type: {type(e).__name__}")
                print(f"Error Message: {str(e)}")
                print(f"{'-'*70}\n")
                
                if attempts >= max_attempts:
                    print(f"Max retries ({max_attempts}) exhausted.")
                    return "# LLM error: request failed"
                
                # Exponential backoff with jitter
                exponential_wait = base_backoff * (2 ** (attempts - 1))
                jitter = random.uniform(0, 1)
                wait_time = min(exponential_wait + jitter, 30)
                
                print(f"[WAIT] Waiting {wait_time:.2f} seconds before retry...")
                time.sleep(wait_time)
            
            except Exception as e:
                print(f"\n[ERROR] Unexpected LLM error: {type(e).__name__}: {e}")
                return "# LLM error: unable to generate code"
        
        return "# LLM retries exhausted"