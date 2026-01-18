import requests
import re
import time
import random
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Look for .env file in project root (up to 5 levels from this file)
    env_path = Path(__file__).resolve()
    for _ in range(5):
        env_path = env_path.parent
        env_file = env_path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break
except ImportError:
    # python-dotenv not installed, will rely on system environment variables
    pass


class LLMClient:
    """A unified client to interact with LLM providers (Ollama or OpenAI).

    Simple wrapper that exposes a `generate_code(prompt)` method. It maps a
    text response to a Python code block (```python ... ```) when present.
    
    Supports two providers:
    - "ollama": University's local Ollama instance (free, requires VPN)
    - "openai": OpenAI API (requires API key, costs money)
    """

    def __init__(
        self,
        provider: str = "ollama",  # "ollama" or "openai"
        base_url: str = "http://rhaegal.dimis.fim.uni-passau.de:15343",
        model_name: str = "codellama:7b",  # For Ollama: codellama:7b; For OpenAI: gpt-4o, gpt-4o-mini
        api_key: str = None  # OpenAI API key (or set OPENAI_API_KEY env var)
    ):
        """Initialize LLM client.
        
        Args:
            provider: LLM provider - "ollama" or "openai"
            base_url: Base URL (for Ollama only)
            model_name: Model to use
                - Ollama: "codellama:7b" (fast), "deepseek-coder-v2:16b" (better quality)
                - OpenAI: "gpt-4o" (best), "gpt-4o-mini" (cheap)
            api_key: OpenAI API key (only needed for provider="openai")
        """
        self.provider = provider.lower()
        self.model = model_name
        
        if self.provider == "ollama":
            self.base_url = base_url.rstrip('/')
            self.generate_endpoint = f"{self.base_url}/api/generate"
            self.api_key = None
        elif self.provider == "openai":
            # OpenAI setup
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                    "or pass api_key parameter."
                )
            self.openai_endpoint = "https://api.openai.com/v1/chat/completions"
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'ollama' or 'openai'.")

    def generate_code(self, prompt: str) -> str:
        """Generate text and return the Python code block (or plain text).

        Retries on network/server errors with exponential backoff + jitter.
        Returns a sentinel string when retries are exhausted or on unrecoverable errors.
        """
        if self.provider == "ollama":
            return self._generate_ollama(prompt)
        elif self.provider == "openai":
            return self._generate_openai(prompt)
        else:
            return "# LLM error: unknown provider"
    
    def _generate_ollama(self, prompt: str) -> str:
        """Generate code using Ollama."""
        attempts = 0
        base_backoff = 2
        max_attempts = 3
        
        while attempts < max_attempts:
            try:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
                
                response = requests.post(
                    self.generate_endpoint,
                    json=payload,
                    timeout=120
                )
                
                if response.status_code != 200:
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}: {response.text}"
                    )
                
                result = response.json()
                text = result.get("response", "")
                
                return self._extract_code(text)
            
            except requests.exceptions.Timeout:
                attempts += 1
                print(f"\n[TIMEOUT] Timeout error (Attempt {attempts}/{max_attempts})")
                if attempts >= max_attempts:
                    print(f"Max retries ({max_attempts}) exhausted.")
                    return "# LLM error: timeout"
                
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
                
                exponential_wait = base_backoff * (2 ** (attempts - 1))
                jitter = random.uniform(0, 1)
                wait_time = min(exponential_wait + jitter, 30)
                
                print(f"[WAIT] Waiting {wait_time:.2f} seconds before retry...")
                time.sleep(wait_time)
            
            except Exception as e:
                print(f"\n[ERROR] Unexpected LLM error: {type(e).__name__}: {e}")
                return "# LLM error: unable to generate code"
        
        return "# LLM retries exhausted"
    
    def _generate_openai(self, prompt: str) -> str:
        """Generate code using OpenAI API."""
        attempts = 0
        base_backoff = 1
        max_attempts = 3
        
        while attempts < max_attempts:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert Python developer. Generate clean, correct Python code based on the user's request."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.2,  # Low temperature for more consistent code generation
                    "max_tokens": 2000
                }
                
                response = requests.post(
                    self.openai_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code != 200:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", error_msg)
                    except:
                        pass
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}: {error_msg}"
                    )
                
                result = response.json()
                text = result["choices"][0]["message"]["content"]
                
                return self._extract_code(text)
            
            except requests.exceptions.Timeout:
                attempts += 1
                print(f"\n[TIMEOUT] OpenAI timeout (Attempt {attempts}/{max_attempts})")
                if attempts >= max_attempts:
                    return "# LLM error: timeout"
                
                wait_time = base_backoff * (2 ** (attempts - 1))
                print(f"[WAIT] Waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
            
            except requests.exceptions.RequestException as e:
                attempts += 1
                print(f"\n[ERROR] OpenAI request error (Attempt {attempts}/{max_attempts}): {e}")
                if attempts >= max_attempts:
                    return "# LLM error: request failed"
                
                wait_time = base_backoff * (2 ** (attempts - 1))
                time.sleep(wait_time)
            
            except Exception as e:
                print(f"\n[ERROR] OpenAI error: {type(e).__name__}: {e}")
                return "# LLM error: unable to generate code"
        
        return "# LLM retries exhausted"
    
    def _extract_code(self, text: str) -> str:
        """Extract Python code block from text, or return text as-is."""
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